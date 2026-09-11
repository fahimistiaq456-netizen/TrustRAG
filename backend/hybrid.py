"""High-level hybrid intelligence pipeline (source-first).

User query -> retrieve top-k -> source gate -> RAG answer (verified, cited) when
the source library matches strongly; otherwise the local model answers naturally.

Why source-first: routing is driven by the evidence, not by a fallible LLM judge.
A compact local model can produce a polished-but-empty answer instead of an
explicit refusal; when the user's source library contains the answer, the
retrieval gate cannot make that mistake.

Pipeline:
  1. Retrieve the top-k chunks from the FAISS source index.
  2. Evidence confidence = average top-3 similarity (should_abstain).
  3. When evidence is strong enough (>= HALLUFIX_ABSTENTION_THRESHOLD), answer
     from the source: grounded generation, sentence verification, citations.
  4. Otherwise (weak or no evidence), return the local model answer.
  5. A RAG answer that verification rejects falls back to the highest-matching
     verbatim source sentence, then to abstention if nothing remains.

Every decision is appended to logs/hybrid_decisions.json.
"""
from __future__ import annotations

import json
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from .abstention import ABSTENTION_MESSAGE, should_abstain
from .decision_engine import MODE_ABSTAIN, MODE_LLM, MODE_RAG, Decision
from .generator import candidate_sentences, generate_answer, question_terms
from .local_llm import LocalLLMError, chat, model_name
from .retriever import best_source_sentence, citation, retrieve
from .vectorstore import LocalVectorStore
from .verifier import verification_summary, verify_answer

NORMAL_SYSTEM_PROMPT = (
    "You are a friendly, helpful assistant. Hold a natural everyday conversation. "
    "Do not claim to search a private handbook or cite documents unless the user supplies them."
)

HYBRID_LOG_PATH = Path("logs") / "hybrid_decisions.json"


def _load_store() -> LocalVectorStore:
    store = LocalVectorStore(os.getenv("HALLUFIX_INDEX_DIR", "data/index"))
    store.load()
    return store


def log_hybrid_decision(record: dict[str, Any]) -> None:
    """Append one decision record to the human-readable audit log."""
    HYBRID_LOG_PATH.parent.mkdir(exist_ok=True, parents=True)
    line = json.dumps(record, ensure_ascii=False)
    with HYBRID_LOG_PATH.open("a", encoding="utf-8") as handle:
        handle.write(line + "\n")


def _empty_verification_summary() -> dict[str, Any]:
    return {"supported_claims": 0, "unsupported_claims": 0, "claims_checked": 0, "claims_supported": 0, "support_rate": 1.0}


def _build_llm_payload(answer: str, started: float, confidence: float, reason: str) -> dict[str, Any]:
    """Natural local-model answer; no retrieval involved."""
    return {
        "answer": answer,
        "mode": MODE_LLM,
        "confidence": confidence,
        "sources": [],
        "verification": [],
        "verification_summary": _empty_verification_summary(),
        "abstained": False,
        "reason": reason,
        "stats": {"latency_ms": round((time.perf_counter() - started) * 1000), "claims_checked": 0, "claims_supported": 0, "support_rate": 1.0, "model": model_name()},
    }


def _build_rag_payload(question: str, chunks: list[dict[str, Any]], started: float, confidence: float, reason: str) -> dict[str, Any]:
    """Answer from the source library: grounded generation, verification, citations."""
    generated = generate_answer(question, chunks)
    if generated == ABSTENTION_MESSAGE:
        # The generator deliberately abstained (no relevant evidence, or the
        # question asks for an aspect the source does not state). Do not verify
        # an abstention and do not override it with a guessed answer.
        verified, verification = generated, []
    else:
        verified, verification = verify_answer(generated, chunks)
        # Only salvage a *generated* answer that verification rejected. If the
        # generator itself abstained, respect that instead of overriding.
        if verified == ABSTENTION_MESSAGE:
            fallback = best_source_sentence(question, chunks)
            if fallback:
                verified = fallback
                verification.append({
                    "claim": fallback,
                    "supported": True,
                    "confidence": 1.0,
                    "reason": "Returned verbatim from the highest-matching retrieved source sentence after generated wording was rejected.",
                })
    supported = sum(1 for item in verification if item["supported"])
    return {
        "answer": verified,
        "mode": MODE_RAG,
        "confidence": confidence,
        "sources": [{"file": c["document_name"], "page": c.get("page_number"), "citation": citation(c), "similarity_score": c["similarity_score"], "text": c["text"]} for c in chunks[:5]],
        "verification": verification,
        "verification_summary": verification_summary(verification),
        "abstained": verified == ABSTENTION_MESSAGE,
        "reason": reason,
        "stats": {"latency_ms": round((time.perf_counter() - started) * 1000), "claims_checked": len(verification), "claims_supported": supported, "support_rate": round(supported / len(verification), 2) if verification else 1.0, "model": model_name()},
    }


def _build_abstain_payload(started: float, reason: str) -> dict[str, Any]:
    """Nothing reliable was found anywhere."""
    return {
        "answer": ABSTENTION_MESSAGE,
        "mode": MODE_ABSTAIN,
        "confidence": 0.0,
        "sources": [],
        "verification": [],
        "verification_summary": _empty_verification_summary(),
        "abstained": True,
        "reason": reason,
        "stats": {"latency_ms": round((time.perf_counter() - started) * 1000), "claims_checked": 0, "claims_supported": 0, "support_rate": 0.0, "model": model_name()},
    }


def _local_chat(question: str) -> str:
    messages = [{"role": "system", "content": NORMAL_SYSTEM_PROMPT}, {"role": "user", "content": question}]
    return chat(messages, temperature=0.7)


def run_hybrid(question: str, load_store: Callable[[], LocalVectorStore] = _load_store) -> dict[str, Any]:
    """Source-first hybrid pipeline: strict extractive answer, else local answer.

    The routing decision is whether the source library *actually answers* the
    question (a verbatim, relevant source sentence was found by the strict
    extractive generator), NOT the retrieval similarity score alone. A compact
    local model must never be allowed to answer a source question it would
    answer from memory (hallucination); it is only used when the source does
    not contain a direct answer.
    """
    started = time.perf_counter()
    chunks: list[dict[str, Any]] = []
    index_exists = True
    llm_answer = ""

    try:
        store = load_store()
        chunks = retrieve(store, question)
    except FileNotFoundError:
        # No source index has been built; the local model must handle it alone.
        index_exists = False
        chunks = []

    threshold = float(os.getenv("HALLUFIX_ABSTENTION_THRESHOLD", "0.25"))
    _, evidence_confidence = should_abstain(chunks, threshold)  # diagnostic only

    # Answerability is decided by the strict extractive generator. A low
    # similarity must not send an entity question to the local model, and a
    # high similarity does not grant the local model permission to include the
    # contents of every retrieved document.
    source_answer = ""
    topic_known_to_source = False
    if index_exists and chunks:
        source_answer = generate_answer(question, chunks)
        # Does the source library recognise the question's topic at all? If it
        # does, but still cannot answer (e.g. the question asks for an aspect
        # the source does not state), the local model must not be allowed to
        # guess: abstain instead.
        terms = question_terms(question)
        topic_known_to_source = bool(terms) and any(
            bool(terms & set(re.findall(r"[a-z0-9]+", sentence.lower())))
            for sentence, _ in candidate_sentences(chunks)
        )
    source_has_answer = bool(source_answer) and source_answer != ABSTENTION_MESSAGE

    if source_has_answer:
        # The source library directly answers the question: trust and verify it.
        decision = Decision(
            MODE_RAG,
            f"Source library contains a direct verbatim answer (similarity {evidence_confidence:.2f}); returning the grounded source sentence.",
        )
        try:
            payload = _build_rag_payload(question, chunks, started, evidence_confidence, decision.reason)
        except LocalLLMError as exc:
            # Grounded generation unavailable: degrade to the natural answer.
            llm_answer = _local_chat(question)
            decision = Decision(MODE_LLM, f"Source generation unavailable ({exc}); returned the local model answer.")
            payload = _build_llm_payload(llm_answer, started, 1.0, decision.reason)
    elif topic_known_to_source:
        # The source is the authority on this topic but does not state the
        # requested information: abstain instead of guessing or hallucinating.
        decision = Decision(
            MODE_ABSTAIN,
            "The source library covers this topic but does not state the requested information; abstaining instead of guessing.",
        )
        payload = _build_abstain_payload(started, decision.reason)
    else:
        # No verbatim source answer -> answer locally (or abstain).
        try:
            llm_answer = _local_chat(question)
        except LocalLLMError:
            if chunks:
                # Local model unavailable but an index exists: attempt the source anyway.
                decision = Decision(MODE_RAG, f"Local model unavailable; using source evidence ({evidence_confidence:.2f}).")
                payload = _build_rag_payload(question, chunks, started, evidence_confidence, decision.reason)
            else:
                raise
        else:
            reason_part = (
                f"No verbatim source answer found ({evidence_confidence:.2f} similarity); "
                if index_exists and chunks else (
                    "No source index available; " if not index_exists else "No source evidence matched; "
                )
            )
            decision = Decision(MODE_LLM, reason_part + "returned the local model answer.")
            payload = _build_llm_payload(llm_answer, started, 1.0, decision.reason)

    log_hybrid_decision({
        "question": question,
        "llm_answer": llm_answer,
        "rag_answer": payload.get("answer", ""),
        "decision": decision.mode,
        "reason": decision.reason,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })
    if not index_exists:
        payload["fallback_unavailable"] = True
    return payload