"""Hybrid (source-first) pipeline unit tests.

Routing rule under test:
  1. Strong source evidence (confidence >= threshold) -> answer from source (RAG).
  2. Weak / missing source evidence -> local model answer (LLM).
  3. RAG path whose verification rejects everything falls back to a verbatim
     source sentence, then to abstention.
"""
from backend import hybrid as h
from backend.abstention import ABSTENTION_MESSAGE
from backend.decision_engine import MODE_ABSTAIN, MODE_LLM, MODE_RAG, make_decision
from backend.hybrid_evaluator import _extract_json, normalize


def _chunk(score: float, text: str = "Asifur is a sweet boy from Muktijuddha hall.") -> dict:
    return {
        "document_name": "handbook.pdf",
        "page_number": 1,
        "chunk_id": "chunk-1",
        "text": text,
        "similarity_score": score,
    }


STRONG = [_chunk(0.575), _chunk(0.50, "Rawnak is department head of computer science."), _chunk(0.48)]
WEAK = [_chunk(0.12)]


def _verify_ok(answer: str, chunks: list[dict]):
    return answer, [{"supported": True, "confidence": 1.0, "reason": "matched"}]


# ---------------------------------------------------------------------------
# Source-first run_hybrid behaviour
# ---------------------------------------------------------------------------

def test_strong_source_answers_from_source(monkeypatch):
    monkeypatch.setattr(h, "retrieve", lambda *a, **k: STRONG)
    monkeypatch.setattr(h, "should_abstain", lambda *a, **k: (False, (0.575 + 0.50 + 0.48) / 3))
    monkeypatch.setattr(h, "log_hybrid_decision", lambda r: None)
    monkeypatch.setattr(h, "generate_answer", lambda q, c: "Asifur is a sweet boy from Muktijuddha hall.")
    monkeypatch.setattr(h, "verify_answer", _verify_ok)
    result = h.run_hybrid("who is asifur", load_store=lambda: object())
    assert result["mode"] == "RAG"
    assert "Asifur" in result["answer"]
    assert result["sources"]


def test_no_evidence_uses_local_model(monkeypatch):
    monkeypatch.setattr(h, "retrieve", lambda *a, **k: [])
    monkeypatch.setattr(h, "should_abstain", lambda *a, **k: (True, 0.0))
    monkeypatch.setattr(h, "chat", lambda *a, **k: "Python is a programming language.")
    monkeypatch.setattr(h, "log_hybrid_decision", lambda r: None)
    result = h.run_hybrid("what is python", load_store=lambda: object())
    assert result["mode"] == "LLM"
    assert result["answer"] == "Python is a programming language."


def test_weak_evidence_uses_local_model(monkeypatch):
    monkeypatch.setattr(h, "retrieve", lambda *a, **k: WEAK)
    monkeypatch.setattr(h, "should_abstain", lambda *a, **k: (True, 0.12))
    monkeypatch.setattr(h, "chat", lambda *a, **k: "I do not know this offhand.")
    monkeypatch.setattr(h, "log_hybrid_decision", lambda r: None)
    result = h.run_hybrid("obscure thing", load_store=lambda: object())
    assert result["mode"] == "LLM"
    assert result["answer"] == "I do not know this offhand."
def test_no_index_uses_local_model_with_flag(monkeypatch):
    def no_index():
        raise FileNotFoundError("no index")

    monkeypatch.setattr(h, "should_abstain", lambda *a, **k: (True, 0.0))
    monkeypatch.setattr(h, "chat", lambda *a, **k: "I can help with general facts.")
    monkeypatch.setattr(h, "log_hybrid_decision", lambda r: None)
    result = h.run_hybrid("hello", load_store=no_index)
    assert result["mode"] == "LLM"
    assert result.get("fallback_unavailable") is True


def test_rag_abstains_when_verification_rejects_everything(monkeypatch):
    monkeypatch.setattr(h, "retrieve", lambda *a, **k: STRONG)
    monkeypatch.setattr(h, "should_abstain", lambda *a, **k: (False, 0.52))
    monkeypatch.setattr(h, "log_hybrid_decision", lambda r: None)
    monkeypatch.setattr(h, "generate_answer", lambda q, c: "Some invented claim.")
    monkeypatch.setattr(h, "verify_answer", lambda a, c: (ABSTENTION_MESSAGE, []))
    monkeypatch.setattr(h, "best_source_sentence", lambda q, c: None)
    result = h.run_hybrid("who is asifur", load_store=lambda: object())
    assert result["mode"] == "RAG"
    assert result["abstained"] is True
    assert result["answer"] == ABSTENTION_MESSAGE


def test_rag_falls_back_to_verbatim_source_sentence(monkeypatch):
    monkeypatch.setattr(h, "retrieve", lambda *a, **k: STRONG)
    monkeypatch.setattr(h, "should_abstain", lambda *a, **k: (False, 0.52))
    monkeypatch.setattr(h, "log_hybrid_decision", lambda r: None)
    monkeypatch.setattr(h, "generate_answer", lambda q, c: "The generated claim.")
    monkeypatch.setattr(h, "verify_answer", lambda a, c: (ABSTENTION_MESSAGE, []))
    monkeypatch.setattr(h, "best_source_sentence", lambda q, c: "Asifur is a sweet boy from Muktijuddha hall.")
    result = h.run_hybrid("who is asifur", load_store=lambda: object())
    assert result["mode"] == "RAG"
    assert "Asifur" in result["answer"]


def test_entity_question_routes_to_rag_even_with_low_similarity(monkeypatch):
    """The local model must not hallucinate an entity the source identifies.

    Retrieval similarity being low must NOT send an entity question to the
    local model (AGENT section 21/23): answerability is decided by whether the
    strict extractive generator found a verbatim source answer.
    """
    chunks = [
        _chunk(0.12, "Rawnak ara chowdhuri is our department head of computer science at Mymensing Engineering college.")
    ]
    monkeypatch.setattr(h, "retrieve", lambda *a, **k: chunks)
    monkeypatch.setattr(h, "should_abstain", lambda *a, **k: (True, 0.12))  # low similarity
    monkeypatch.setattr(h, "log_hybrid_decision", lambda r: None)
    monkeypatch.setattr(h, "generate_answer", lambda q, c: chunks[0]["text"])
    monkeypatch.setattr(h, "verify_answer", _verify_ok)
    result = h.run_hybrid("Who is Rawnak Ara?", load_store=lambda: object())
    assert result["mode"] == "RAG"
    assert "Rawnak ara chowdhuri is our department head" in result["answer"]


def test_unsupported_aspect_abstains_instead_of_local_hallucination(monkeypatch):
    """If the source covers a topic but lacks an aspect (e.g. research), the
    local model is never allowed to invent it - hybrid abstains."""
    chunks = [_chunk(0.5, "Rawnak Ara is the department head of Computer Science.")]
    monkeypatch.setattr(h, "retrieve", lambda *a, **k: chunks)
    monkeypatch.setattr(h, "should_abstain", lambda *a, **k: (False, 0.5))
    monkeypatch.setattr(h, "log_hybrid_decision", lambda r: None)
    monkeypatch.setattr(h, "generate_answer", lambda q, c: ABSTENTION_MESSAGE)
    # If the local model were used, it would hallucinate research info.
    monkeypatch.setattr(h, "chat", lambda *a, **k: "Rawnak conducts research on image processing.")
    result = h.run_hybrid("What research does Rawnak Ara conduct?", load_store=lambda: object())
    assert result["mode"] == MODE_ABSTAIN
    assert result["abstained"] is True
    assert result["answer"] == ABSTENTION_MESSAGE


# ---------------------------------------------------------------------------
# decision_engine helper (kept available as a judge-based policy).
# ---------------------------------------------------------------------------

def test_known_question_keeps_llm_answer():
    evaluation = {"quality_score": 0.95, "supported": True, "needs_rag": False, "reason": "fine"}
    assert make_decision(evaluation, has_evidence=True, evidence_confidence=0.6).mode == MODE_LLM


def test_unknown_local_but_in_documents_switches_to_rag():
    evaluation = {"quality_score": 0.1, "supported": False, "needs_rag": True, "reason": "evidence answers it"}
    assert make_decision(evaluation, has_evidence=True, evidence_confidence=0.85).mode == MODE_RAG


def test_unknown_everywhere_abstains_legacy_helper():
    evaluation = {"quality_score": 0.0, "supported": False, "needs_rag": True, "reason": "nothing"}
    assert make_decision(evaluation, has_evidence=False, evidence_confidence=0.0).mode == MODE_ABSTAIN


# ---------------------------------------------------------------------------
# Evaluator parsing helpers (regression coverage).
# ---------------------------------------------------------------------------

def test_extract_json_strips_markdown_fences():
    raw = "```json\n{\"quality_score\": 0.8, \"supported\": true, \"needs_rag\": false, \"reason\": \"ok\"}\n```"
    parsed = _extract_json(raw)
    assert parsed["quality_score"] == 0.8
    assert parsed["supported"] is True


def test_normalize_accepts_string_booleans_and_aliases():
    raw = {"quality_score": "0.7", "supported": "true", "needs_fallback": True, "reason": "fine"}
    normalized = normalize(raw)
    assert normalized["quality_score"] == 0.7
    assert normalized["supported"] is True
    assert normalized["needs_rag"] is True