"""Reusable metric helpers for multi-domain evaluation.

Kept pure and deterministic so they can be unit-tested without a live API or
expensive models.
"""
from __future__ import annotations

import re
from typing import Iterable, Optional


def _mean(values: list[float]) -> float:
    return round(sum(values) / len(values), 3) if values else 0.0


def recall_at_k(relevant: list[str], retrieved: list[str], k: int = 5) -> Optional[float]:
    rel = set(relevant)
    if not rel:
        return None
    hits = len(rel & set(retrieved[:k]))
    return round(hits / len(rel), 3)


def precision_at_k(relevant: list[str], retrieved: list[str], k: int = 5) -> Optional[float]:
    rel = set(relevant)
    if not rel:
        return 0.0
    top = retrieved[:k]
    return round(len(rel & set(top)) / k, 3) if top else 0.0


def mrr(relevant: list[str], retrieved: list[str]) -> Optional[float]:
    rel = set(relevant)
    if not rel:
        return None
    for rank, key in enumerate(retrieved, start=1):
        if key in rel:
            return round(1.0 / rank, 3)
    return 0.0


def token_overlap_ratio(text: str, reference: str) -> float:
    """Fraction of reference tokens (len>=4) appearing in the answer."""
    ref_tokens = set(re.findall(r"[a-z0-9]{4,}", reference.lower()))
    if not ref_tokens:
        return 0.0
    ans = set(re.findall(r"[a-z0-9]{4,}", text.lower()))
    return len(ref_tokens & ans) / len(ref_tokens)


def reference_match(answer: str, reference: str, ratio: float = 0.5) -> bool:
    """Grounding-style correctness: answer shares >= `ratio` of reference tokens."""
    return token_overlap_ratio(answer, reference) >= ratio


def abstention_accurate(expected_type: str, abstained: bool) -> bool:
    """For unanswerable/misleading we want an abstention; otherwise we want no abstention."""
    wants_abstain = expected_type in ("unanswerable", "misleading", "contradiction")
    return abstained == wants_abstain


def rate(values: Iterable[bool]) -> float | str:
    present = list(values)
    if not present:
        return "N/A"
    return round(sum(1 for v in present if v) / len(present), 3)


def aggregate(records: Iterable[dict]) -> dict:
    rows = list(records)
    return {
        "n": len(rows),
        "abstention_accuracy": rate([x.get("abstention_accurate") for x in rows if x.get("abstention_accurate") is not None]),
        "answer_correctness": rate([x.get("answer_correct") for x in rows if x.get("answer_correct") is not None]),
        "unsupported_claim_rate": rate([x.get("unsupported_claims", 1) == 0 for x in rows if x.get("unsupported_claims") is not None]),
        "mean_mrr": _mean([float(x["mrr"]) for x in rows if x.get("mrr") is not None]) if any(x.get("mrr") is not None for x in rows) else "N/A",
    }