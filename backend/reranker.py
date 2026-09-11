"""Phase 1 — Cross-encoder reranking.

Placed between FAISS candidate retrieval and context processing:

    FAISS candidates -> Cross-Encoder rerank -> top-N evidence

Design decisions:
  * The retriever stays a pure candidate producer. The reranker is an
    independent stage so the two are not tightly coupled.
  * Model loading is lazy (first use only) and cached as a module singleton
    so we never reload the model per request.
  * If the model cannot be loaded, reranking degrades gracefully: candidates
    are returned unchanged with ``reranked=False`` so the rest of the RAG
    pipeline continues to work.
"""
from __future__ import annotations

import logging
import threading
from typing import Any

from .config import get_settings

logger = logging.getLogger(__name__)

# Singleton + lock so we only ever load the model once, even cross-thread.
_lock = threading.Lock()
_model = None
_model_failed: bool = False


class RerankerError(RuntimeError):
    """Raised when the reranker model cannot be loaded or is unavailable."""


def _model_name() -> str:
    return get_settings().reranker_model


def _load_model():
    """Lazily build and cache the CrossEncoder reranker (thread-safe)."""
    global _model, _model_failed
    if _model is not None:
        return _model
    with _lock:
        if _model is not None:
            return _model
        if _model_failed:
            raise RerankerError(
                f"Reranker model failed to load earlier ({_model_name()})."
            )
        try:
            from sentence_transformers import CrossEncoder

            logger.info("Loading cross-encoder reranker: %s", _model_name())
            _model = CrossEncoder(_model_name(), device="cpu")
        except Exception as exc:  # noqa: BLE001 - any failure must degrade
            _model_failed = True
            raise RerankerError(f"Could not load reranker {_model_name()}: {exc}") from exc
    return _model


def _score_pairs(model, query: str, texts: list[str]) -> list[float]:
    pairs = [(query, text) for text in texts]
    try:
        return [float(score) for score in model.predict(pairs)]
    except Exception as exc:  # noqa: BLE001
        logger.warning("Cross-encoder predict failed: %s", exc)
        raise RerankerError(str(exc)) from exc


def rerank_candidates(
    question: str,
    candidates: list[dict[str, object]],
    candidates_k: int | None = None,
    top_n: int | None = None,
    min_score: float | None = None,
) -> tuple[list[dict[str, object]], bool]:
    """Rerank FAISS candidates with a cross-encoder.

    Returns ``(reranked_chunks, reranked_flag)``. When the reranker is disabled
    or cannot load, the input candidates are returned unchanged with
    ``reranked=False`` (graceful degradation).
    """
    # Early exit: disabled or nothing to rerank.
    if not candidates:
        return candidates, False
    if not get_settings().reranker_enabled:
        return candidates, False

    cfg = get_settings()
    candidates_k = candidates_k or cfg.rerank_candidates
    top_n = top_n or cfg.rerank_top_n
    min_score = min_score if min_score is not None else cfg.rerank_min_score

    try:
        model = _load_model()
    except RerankerError as exc:
        logger.warning("Reranker unavailable; using FAISS order. %s", exc)
        return candidates, False
    if model is None:
        return candidates, False

    head = list(candidates[:candidates_k])
    if len(head) < 2:
        return head, True

    if len(head) > 1:
        # Keep a consistent score key even when a chunk lacks it.
        for chunk in head:
            chunk.setdefault("similarity_score", 0.0)
        texts = [str(chunk["text"]) for chunk in head]
        scores = _score_pairs(model, question, texts)
        for chunk, score in zip(head, scores):
            chunk["reranker_score"] = float(score)

        if min_score > -1.0:
            head = [c for c in head if float(c.get("reranker_score", 0.0)) >= min_score]

        head.sort(key=lambda c: float(c.get("reranker_score", 0.0)), reverse=True)
        head = head[:top_n]

    # Each reranked chunk keeps its FAISS score for provenance / UI.
    return head, True