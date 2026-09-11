"""Conservative pre-generation gate that prevents unsupported API calls."""
from __future__ import annotations

ABSTENTION_MESSAGE = "Insufficient information available in the university handbook."


def should_abstain(chunks: list[dict[str, object]], threshold: float) -> tuple[bool, float]:
    # Use average of top 3 chunks instead of just the max to be more robust
    top_chunks = sorted(chunks, key=lambda c: float(c["similarity_score"]), reverse=True)[:3]
    confidence = sum(float(c["similarity_score"]) for c in top_chunks) / len(top_chunks) if top_chunks else 0.0
    return confidence < threshold, confidence


# Phrases that indicate the local model could not retrieve/answer from its own
# memory. A hybrid (LLM-first, RAG-fallback) mode uses this to decide whether to
# fall back to the indexed source library.
LLM_ABSTENTION_PATTERNS = (
    "i can't answer",
    "i cannot answer",
    "i can't provide",
    "i cannot provide",
    "i don't know",
    "i do not know",
    "i don't have",
    "i do not have",
    "i'm not sure",
    "i am not sure",
    "not sure",
    "insufficient information",
    "no information",
    "no information is available",
    "no information available",
    "doesn't have access",
    "does not have access",
    "don't have access",
    "do not have access",
    "can't help",
    "cannot help",
    "can't answer",
    "not able to answer",
    "not be able to answer",
    "unable to answer",
    "unable to help",
    "no information in",
    "not in the handbook",
    "not in the source",
    "private handbook",
    "private source",
    "no such information",
)


def llm_abstained(text: str) -> bool:
    """Return True when a natural-model response signals it could not answer.

    This is a conservative, transparent heuristic: it looks for refusal /
    uncertainty phrases that compact local models emit when the answer is not
    in their memory. It does not judge factual correctness.
    """
    lowered = (text or "").lower()
    return any(pattern in lowered for pattern in LLM_ABSTENTION_PATTERNS)
