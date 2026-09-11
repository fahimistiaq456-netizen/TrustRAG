"""Tests for Phase 1 — cross-encoder reranking.

Uses mocked model scores so tests never download or run the model. Covers
config gating, top-N selection, min-score filtering, graceful fallback when the
model fails to load, and provenance fields.
"""
from __future__ import annotations

from unittest.mock import patch

import backend.reranker as rr
from backend.config import get_settings


def _chunk(text: str, score: float) -> dict:
    return {"text": text, "similarity_score": score, "document_name": "d.txt", "page_number": 1, "chunk_id": f"c-{score}"}


def _enable(monkeypatch):
    monkeypatch.setattr(get_settings(), "reranker_enabled", True)
    monkeypatch.setattr(get_settings(), "rerank_candidates", 10)
    monkeypatch.setattr(get_settings(), "rerank_top_n", 5)
    monkeypatch.setattr(get_settings(), "rerank_min_score", -10.0)


def test_disabled_returns_candidates_unchanged():
    chunks = [_chunk("alpha", 0.9), _chunk("beta", 0.8)]
    out, reranked = rr.rerank_candidates("q", chunks)
    assert out == chunks
    assert reranked is False


def test_empty_candidates_short_circuits():
    out, reranked = rr.rerank_candidates("q", [])
    assert out == []
    assert reranked is False


def test_rerank_reorders_by_cross_encoder_score(monkeypatch):
    _enable(monkeypatch)
    chunks = [_chunk("alpha", 0.9), _chunk("beta", 0.8), _chunk("gamma", 0.7)]

    # Cross-encoder disagrees with FAISS order: gamma best, alpha worst.
    fake_model = type("Fake", (), {"predict": lambda self, pairs: [0.1, 0.55, 0.95]})()
    with patch.object(rr, "_load_model", return_value=fake_model):
        out, reranked = rr.rerank_candidates("q", chunks)

    assert reranked is True
    assert [c["text"] for c in out] == ["gamma", "beta", "alpha"]
    assert out[0]["reranker_score"] == 0.95
    assert out[0]["similarity_score"] == 0.7  # FAISS score preserved


def test_top_n_limit_respected(monkeypatch):
    _enable(monkeypatch)
    monkeypatch.setattr(get_settings(), "rerank_top_n", 2)
    chunks = [_chunk(f"c{i}", 1.0 - i * 0.1) for i in range(5)]
    fake_model = type("Fake", (), {"predict": lambda self, pairs: [i / 10 for i in range(len(pairs), 0, -1)]})()
    with patch.object(rr, "_load_model", return_value=fake_model):
        out, _ = rr.rerank_candidates("q", chunks)
    assert len(out) == 2


def test_min_score_filters(monkeypatch):
    _enable(monkeypatch)
    monkeypatch.setattr(get_settings(), "rerank_min_score", 0.6)
    chunks = [_chunk("a", 0.9), _chunk("b", 0.8)]
    fake_model = type("Fake", (), {"predict": lambda self, pairs: [0.7, 0.2]})()
    with patch.object(rr, "_load_model", return_value=fake_model):
        out, _ = rr.rerank_candidates("q", chunks)
    assert out == [chunks[0]]


def test_model_load_failure_degrades_gracefully(monkeypatch):
    _enable(monkeypatch)
    chunks = [_chunk("a", 0.9), _chunk("b", 0.8)]

    def boom():
        raise rr.RerankerError("cannot load")

    with patch.object(rr, "_load_model", side_effect=boom):
        out, reranked = rr.rerank_candidates("q", chunks)
    assert out == chunks
    assert reranked is False