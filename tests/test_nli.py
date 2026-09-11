"""Tests for Phase 2 — dedicated NLI verification.

Mocks the NLI model so tests do not download a transformer. Covers the
ENTAILMENT/NEUTRAL/CONTRADICTION mapping, thresholds, graceful fallback when NLI
is disabled/unavailable, and the verifier integration (label + method fields).
"""
from __future__ import annotations

from unittest.mock import patch

import backend.nli as nli
from backend.verifier import _judge_by_nli, verify_answer


def _enable_nli(monkeypatch):
    from backend.config import get_settings
    cfg = get_settings()
    cfg.nli_enabled = True
    cfg.nli_entailment_threshold = 0.70
    cfg.nli_contradiction_threshold = 0.70


def test_disabled_classify_returns_none():
    assert nli.classify("claim", "evidence") is None


def test_nli_maps_scores_to_labels(monkeypatch):
    _enable_nli(monkeypatch)
    fake = type("Fake", (), {"predict": lambda self, pairs: [[0.1, 0.8, 0.1]]})()
    with patch.object(nli, "load_model", return_value=fake):
        result = nli.classify("claim", "evidence")
    assert result is not None
    assert result.label == "ENTAILMENT"
    assert result.method == "nli"


def test_nli_contradiction(monkeypatch):
    _enable_nli(monkeypatch)

    # Our default labels = [contradiction, entailment, neutral].
    fake = type("Fake", (), {"predict": lambda self, pairs: [[0.9, 0.05, 0.05]]})()
    with patch.object(nli, "load_model", return_value=fake):
        result = nli.classify("claim", "evidence")
    assert result.label == "CONTRADICTION"
    assert nli.label_means_supported(result.label) is False


def test_nli_neutral(monkeypatch):
    _enable_nli(monkeypatch)
    fake = type("Fake", (), {"predict": lambda self, pairs: [[0.1, 0.1, 0.8]]})()
    with patch.object(nli, "load_model", return_value=fake):
        result = nli.classify("claim", "evidence")
    assert result.label == "NEUTRAL"


def test_nli_model_unavailable_returns_none(monkeypatch):
    _enable_nli(monkeypatch)

    def boom():
        raise nli.NLIError("offline")

    with patch.object(nli, "load_model", side_effect=boom):
        assert nli.classify("claim", "evidence") is None


def test_verifier_nli_integration(monkeypatch):
    from backend.config import get_settings
    get_settings().nli_enabled = True
    # entailment at index 1; must be strong enough to clear the 0.70 threshold
    fake = type("Fake", (), {"predict": lambda self, pairs: [[0.1, 5.0, 0.1]]})()
    with patch.object(nli, "load_model", return_value=fake):
        result = _judge_by_nli("claim", "evidence")
    assert result["label"] == "ENTAILMENT"
    assert result["method"] == "nli"
    assert result["supported"] is True
    get_settings().nli_enabled = False


def test_verify_answer_still_works_when_nli_disabled(monkeypatch):
    # deterministic fast-path + LLM fallback when NLI is disabled
    def fake_chat(messages, temperature=0.0, json_mode=True):
        return '{"supported": true, "confidence": 0.9, "reason": "ok"}'

    monkeypatch.setattr("backend.verifier.chat", fake_chat)
    chunks = [{"text": "COMPOUND interest is charge.", "document_name": "d", "page_number": 1, "chunk_id": "1"}]
    answer, results = verify_answer("The system is good.", chunks)
    assert answer  # kept a supported claim
    assert results[0]["method"] in ("deterministic", "llm")