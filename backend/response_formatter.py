"""Presentation-only answer formatter.

The formatter is a presentation layer, NOT a knowledge layer. It never adds,
paraphrases, expands, infers, or recombines information. It applies only safe,
lossless cleanup: whitespace collapse, punctuation spacing, and removal of
embedded citation / metadata keys.

The previous "polish into natural prose" pass is intentionally removed: it
produced extra, unsupported wording and combined unrelated facts.
"""
from __future__ import annotations

import re


def _clean_metadata_mentions(text: str) -> str:
    """Best-effort removal of citation keys embedded in the answer text."""
    return re.sub(r"\([^)]*(?:\.pdf|\.txt|chunk[^)]*|p\. \d+|page \d+)[^)]*\)", "", text).strip()


def format_answer(question: str, answer: str, evidence: str = "") -> str:
    """Apply lossless cleanup only; never alters the factual content.

    ``question`` and ``evidence`` are accepted for backward compatibility but
    are not used to change the answer.
    """
    if not answer:
        return ""
    cleaned = _clean_metadata_mentions(answer)
    # Collapse whitespace and normalize space before sentence-ending punctuation.
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    cleaned = re.sub(r"\s+([.!?])", r"\1", cleaned)
    return cleaned or answer