"""Sentence-level verification of claim support.

Verification pipeline (deterministic fast-path is always tried first):

    1. deterministic fast path (exact phrases / precise numbers)
    2. NLI model  (dedicated Natural Language Inference, optional, when enabled)
    3. LLM judge  (logical-support fallback when NLI is off/unavailable)

Each sentence is classified ENTAILMENT / NEUTRAL / CONTRADICTION. A claim is
``supported`` when it is judged ENTAILMENT (by direct match, NLI, or the LLM
judge). Unsupported claims are dropped from the final answer.

This extends, rather than replaces, the previous verification logic so the
pipeline keeps working when NLI is disabled or the model cannot load.
"""
from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass

from . import nli as nli_module
from .local_llm import LocalLLMError, chat
from .retriever import evidence_text


@dataclass(frozen=True)
class VerificationResult:
    claim: str
    supported: bool
    confidence: float
    reason: str
    label: str = "NEUTRAL"
    method: str = "llm"
    evidence: str = ""


def split_sentences(answer: str) -> list[str]:
    """Split prose without breaking abbreviations such as `p. 1` in citations."""
    protected = re.sub(r"\b(p|pp|e\.g|i\.e)\b\.", lambda match: match.group(0).replace(".", "<DOT>"), answer, flags=re.IGNORECASE)
    return [sentence.strip().replace("<DOT>", ".") for sentence in re.split(r"(?<=[.!?])\s+", protected) if sentence.strip()]


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9\s]", " ", text.lower())).strip()


def _directly_supported(claim: str, context: str) -> bool:
    """Deterministic fast-path for facts that literally appear in the evidence.

    The normalized claim (punctuation and case collapsed, whitespace folded) must
    appear verbatim inside the normalized evidence. This correctly accepts a
    real source sentence even when it contains stopwords (e.g. "is our"), and it
    never accepts a paraphrase, inference, or expansion on its own.
    """
    normalized_claim = _normalize(claim)
    normalized_context = _normalize(context)
    if normalized_claim and normalized_claim in normalized_context:
        return True

    # Precise numbers are a special, high-value literal fact: require the exact
    # digits and every remaining content word to be present in the evidence.
    stop_words = {"the", "and", "for", "with", "that", "this", "from", "are", "was", "were", "has", "have", "been", "into", "only", "must"}
    claim_words = [word for word in normalized_claim.split() if len(word) > 2 and word not in stop_words]
    numbers = re.findall(r"\b\d+(?:\.\d+)?\b", claim)
    context_words = set(normalized_context.split())
    all_terms_present = len(claim_words) >= 3 and set(claim_words).issubset(context_words)
    return bool(numbers) and all(number in normalized_context for number in numbers) and all_terms_present


def _judge_support(claim: str, context: str) -> VerificationResult:
    """Ask the local model whether the claim is DIRECTLY supported by the evidence.

    Support is strict: every fact in the claim must appear explicitly in the
    evidence. A light rewording is allowed, but an inference, extrapolation, or
    added detail is considered UNSUPPORTED.
    """
    prompt = f"""Claim: {claim}

Evidence:
{context}

Is this claim directly and explicitly supported by the evidence?

- A claim is SUPPORTED only when EVERY fact it states appears explicitly in the evidence.
- The claim may lightly reword the evidence, but must NOT add, infer, or extrapolate any fact.
- A claim is UNSUPPORTED when the evidence is silent about any part of it, contradicts it,
  or when any fact in it is merely inferred or combined from separate evidence.

Return JSON only: {{"supported": true|false, "confidence": 0.0-1.0, "reason": "brief reason"}}"""
    try:
        raw = chat([{"role": "user", "content": prompt}], temperature=0.0, json_mode=True)
        parsed = json.loads(raw)
        supported = bool(parsed.get("supported"))
        confidence = max(0.0, min(1.0, float(parsed.get("confidence", 0))))
        reason = str(parsed.get("reason", "No reason provided."))
        return VerificationResult(claim, supported, confidence, reason)
    except (LocalLLMError, ValueError, TypeError, json.JSONDecodeError) as exc:
        return VerificationResult(claim, False, 0.0, f"Verification failed safely: {exc}")


def _judge_by_nli(claim: str, context: str) -> dict[str, object] | None:
    """Run the NLI model for a claim; returns None when unavailable/disabled."""
    result = nli_module.classify(claim, context)
    if result is None:
        return None
    supported = nli_module.label_means_supported(result.label)
    if supported:
        # Entailment only counts when it clears the configured threshold.
        supported = result.confidence >= nli_module.threshold(result.label)
    return asdict(VerificationResult(
        claim=claim,
        supported=supported,
        confidence=result.confidence,
        reason=f"NLI label: {result.label}",
        label=result.label,
        method=result.method,
        evidence=context,
    ))


def verify_answer(answer: str, chunks: list[dict[str, object]]) -> tuple[str, list[dict[str, object]]]:
    """Verify every sentence against the evidence; keep only supported claims."""
    context = evidence_text(chunks)
    results: list[dict[str, object]] = []
    for claim in split_sentences(answer):
        if _directly_supported(claim, context):
            results.append(asdict(VerificationResult(claim, True, 1.0, "Direct factual phrase found in retrieved evidence.", "ENTAILMENT", "deterministic", context)))
            continue
        nli_result = _judge_by_nli(claim, context)
        if nli_result is not None:
            results.append(nli_result)
            continue
        results.append(asdict(_judge_support(claim, context)))
    kept = [r["claim"] for r in results if r["supported"]]
    return " ".join(kept) or "Insufficient information available in the university handbook.", results


def verification_summary(verification: list[dict[str, object]]) -> dict[str, object]:
    """Consolidated support statistics for pipeline stats blocks.

    ``supported_claims`` / ``unsupported_claims`` follow the API contract.
    """
    checked = len(verification)
    supported = sum(1 for item in verification if item["supported"])
    return {
        "supported_claims": supported,
        "unsupported_claims": checked - supported,
        "claims_checked": checked,
        "claims_supported": supported,
        "support_rate": round(supported / checked, 2) if checked else 1.0,
    }