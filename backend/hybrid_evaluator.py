"""LLM-judge hybrid answer quality evaluation.

The naive LLM-first pipeline falls back only when the local model *explicitly
says* it does not know. That misses the common case where the model produces a
polished but uncertain or outright incorrect answer. This module uses a second
LLM call as a judge to decide whether the local answer is adequate or whether
the RAG-grounded answer should be used instead.
"""
from __future__ import annotations

import json
import re

from .local_llm import LocalLLMError, chat

EVALUATOR_SYSTEM_PROMPT = (
    "You are an answer quality evaluator for a retrieval-augmented generation "
    "(RAG) system. You judge whether a local language model's answer is good "
    "enough on its own, or whether the system should instead return its "
    "evidence-grounded RAG answer."
)

EVALUATOR_PROMPT = """Question:
{question}

LLM Answer:
{answer}

Retrieved Evidence:
{evidence}

Evaluate the LLM Answer and Return ONLY valid JSON with exactly these keys:
{{"quality_score": 0.0-1.0, "supported": true/false, "needs_rag": true/false, "reason": "short explanation"}}

Rules:
- "quality_score": 0.0 to 1.0 measuring how correct and complete the answer is.
- "supported": true when the answer plausibly answers the question (either it is
  grounded in the retrieved evidence, or the question is general knowledge for
  which no evidence is needed). false when the answer is a refusal such as
  "I don't know", is irrelevant, or states facts with no support.
- "needs_rag": true when using the retrieved evidence would clearly give a better
  answer (the local answer is uncertain, refuses, missing the point, or
  hallucinates). false when the local answer is already good enough.
- "reason": one short sentence summarizing the judgement.
"""


def _extract_json(text: str) -> dict:
    """Parse a JSON object, tolerating markdown code fences from compact models."""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    cleaned = cleaned.strip()
    if not cleaned.startswith("{"):
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start != -1 and end != -1:
            cleaned = cleaned[start : end + 1]
    return json.loads(cleaned)


def _clamp(value, low: float = 0.0, high: float = 1.0) -> float:
    try:
        return max(low, min(high, float(value)))
    except (TypeError, ValueError):
        return 0.0


def normalize(raw: dict) -> dict:
    """Coerce an evaluator dict into canonical keys the decision engine expects."""
    quality = raw.get("quality_score", raw.get("score", raw.get("quality", 0)))
    supported = raw.get("supported")
    needs_rag = raw.get("needs_rag", raw.get("needs_fallback", raw.get("needs_abstention", False)))
    reason = raw.get("reason", "No rationale provided.") or "No rationale provided."
    if isinstance(supported, str):
        supported = supported.strip().lower() in {"true", "yes", "1"}
    if isinstance(needs_rag, str):
        needs_rag = needs_rag.strip().lower() in ("true", "yes", "1")
    return {
        "quality_score": _clamp(quality),
        "supported": bool(supported),
        "needs_rag": bool(needs_rag),
        "reason": str(reason).strip(),
    }


def evaluate_answer(question: str, llm_answer: str, evidence: str) -> dict:
    """Run the judge over the local answer and the retrieved evidence.

    Returns a canonical dict:
        {"quality_score": float, "supported": bool, "needs_rag": bool, "reason": str}
    """
    default = {
        "quality_score": 0.0,
        "supported": not bool(evidence),
        "needs_fallback": not bool(evidence),
        "reason": "Evaluation unavailable; defaulting to a safe decision.",
    }
    prompt = EVALUATOR_PROMPT.format(question=question, answer=llm_answer, evidence=evidence or "No evidence was retrieved.")
    try:
        raw = chat(
            [
                {"role": "system", "content": EVALUATOR_SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            temperature=0.0,
            json_mode=True,
        )
        parsed = _extract_json(raw)
    except (LocalLLMError, ValueError, TypeError, json.JSONDecodeError) as exc:
        parsed = {**default, "reason": f"Judge error (safe default): {exc}"}
    return normalize(parsed)