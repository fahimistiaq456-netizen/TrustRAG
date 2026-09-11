"""Hybrid decision engine: selects LLM, RAG, or ABSTAIN as the final answer.

The decision is driven by the LLM-judge evaluation (hybrid_evaluator) combined
with whether the retrievers actually produced usable evidence. Switching happens
*after* both the local answer and the retrieved context are available, so the
judge can confirm whether the local answer is adequate before we discard it.
"""
from __future__ import annotations

from dataclasses import dataclass

MODE_LLM = "LLM"
MODE_RAG = "RAG"
MODE_ABSTAIN = "ABSTAIN"


@dataclass(frozen=True)
class Decision:
    mode: str
    reason: str


def make_decision(
    evaluation: dict,
    has_evidence: bool,
    evidence_confidence: float,
) -> Decision:
    """Decide which pipeline should produce the final answer.

    Args:
        evaluation: canonical dict from hybrid_evaluator with keys
            quality_score, supported, needs_rag, reason.
        has_evidence: whether the retriever returned at least one usable chunk.
        evidence_confidence: the abstention confidence (avg top-3 similarity).

    Returns:
        A Decision describing the selected mode:
            LLM     - the local answer is already good enough.
            RAG     - the local answer is inadequate and relevant evidence exists.
            ABSTAIN - neither the local answer nor the evidence is usable.
    """
    needs_rag = evaluation.get("needs_rag", False)
    supported = evaluation.get("supported", False)
    quality = evaluation.get("quality_score", 0.0)
    judge_reason = evaluation.get("reason", "No rationale provided.")

    if not needs_rag and (supported or quality >= 0.5):
        # The judge believes the local model answered acceptably.
        return Decision(MODE_LLM, f"LLM answer is sufficient ({judge_reason})")

    if has_evidence and evidence_confidence > 0.0:
        # The local answer fell short but evidence exists: switch to RAG.
        return Decision(MODE_RAG, f"Using evidence-grounded answer ({judge_reason})")

    # No useful answer from memory and no usable evidence: abstain.
    return Decision(MODE_ABSTAIN, f"No reliable answer found ({judge_reason})")