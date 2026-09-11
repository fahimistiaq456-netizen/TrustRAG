"""Tests for the natural generation pipeline.

Covers:
- context preprocessing (valid sentences, boundary merging, dedupe, metadata)
- sentence-aware chunking (800 / 150)
- generator flow (cleaned context -> summary -> natural answer)
- verifier logical-support judging
- new API response format (sources file/page, verification_summary)
"""
from unittest.mock import patch

import backend.hybrid as hybrid
from backend.context_processor import (
    deduplicate_sentences,
    extract_complete_sentences,
    is_valid_sentence,
    preprocess_context,
    split_sentences,
    summarize_evidence,
)
from backend.generator import INSUFFICIENT_MESSAGE, generate_answer
from backend.ingest import CHUNK_OVERLAP, CHUNK_SIZE, sentence_chunks
from backend.verifier import verify_answer, verification_summary


# ---------------------------------------------------------------------------
# Context preprocessing layer
# ---------------------------------------------------------------------------

def test_sentence_validity_rules():
    assert is_valid_sentence("HalluFlow reduces hallucination using RAG.")
    assert is_valid_sentence("Does the handbook mention grading policies?")
    assert not is_valid_sentence("Short sentence.")                  # < 5 words
    assert not is_valid_sentence("the system improves accuracy.")  # lowercase start
    assert not is_valid_sentence("No terminator here")            # no end punctuation
    assert not is_valid_sentence("Chapter 11: Future Work")       # heading fragment


def test_split_sentences_protects_abbreviations():
    parts = split_sentences("See p. 27 for details. The system works well.")
    assert parts == ["See p. 27 for details.", "The system works well."]


def test_extract_complete_sentences_merges_across_chunk_boundary():
    chunks = [
        {"text": "The future improvements aim to make HalluFlow more accurate"},
        {"text": "and scalable for real-world deployment."},
    ]
    sentences = extract_complete_sentences(chunks)
    assert "The future improvements aim to make HalluFlow more accurate and scalable for real-world deployment." in sentences


def test_deduplicate_sentences():
    sentences = ["The system improves accuracy.", "The system improves accuracy.", "Another claim here."]
    assert deduplicate_sentences(sentences) == ["The system improves accuracy.", "Another claim here."]


def test_preprocess_context_drops_headings_and_fragments():
    chunks = [
        {"text": "Chapter 11: Future Work", "document_name": "doc.pdf", "page_number": 1},
        {"text": "The system improves scalability through embedding. future work will", "document_name": "doc.pdf", "page_number": 1},
        {"text": "continue focusing on accuracy improvements.", "document_name": "doc.pdf", "page_number": 2},
    ]
    result = preprocess_context(chunks)
    assert all(is_valid_sentence(s) for s in result["sentences"])
    assert any("scalability through embedding" in s for s in result["sentences"])
    assert "Chapter 11" not in result["evidence"]
    assert len(result["metadata"]) == 2  # page 1 and page 2, de-duplicated


def test_summarize_evidence_is_extractive_and_never_adds_facts():
    sentences = ["The system improves accuracy.", "It also scales well.", "Another unrelated claim entirely."]
    summary = summarize_evidence("What does it do?", sentences)
    assert "accuracy" in summary
    assert "scales well" in summary
    # Extractive compression: sentences are joined verbatim, never rewritten.
    assert summary == " ".join(sentences[:8])
# ---------------------------------------------------------------------------
# Chunking
# ---------------------------------------------------------------------------

def test_chunk_size_defaults_are_800_and_150():
    assert CHUNK_SIZE == 800
    assert CHUNK_OVERLAP == 150


def test_sentence_chunks_do_not_split_sentences():
    text = " ".join(
        f"The registration period for semester {i} opens early in the year." for i in range(1, 20)
    )
    chunks = sentence_chunks(text)
    assert len(chunks) > 1
    for chunk in chunks:
        assert chunk.startswith("The registration period")


def test_sentence_chunks_respect_size_budget():
    text = " ".join(
        f"Academic warning applies when the GPA falls below threshold {i} for a semester." for i in range(1, 30)
    )
    chunks = sentence_chunks(text, chunk_size=200, chunk_overlap=40)
    assert len(chunks) > 1
    # No single chunk may exceed the budget by more than one overlap sentence.
    assert all(len(c) <= 260 for c in chunks)


# ---------------------------------------------------------------------------
# Natural generator flow
# ---------------------------------------------------------------------------

def test_generate_answer_returns_insufficient_when_no_valid_sentences(monkeypatch):
    chunks = [{"text": "Chapter 11: Future Work only headings", "document_name": "d.pdf", "page_number": 1}]
    answer = generate_answer("What is future work?", chunks)
    assert answer == INSUFFICIENT_MESSAGE


def test_generate_answer_returns_verbatim_source_sentence():
    chunks = [
        {
            "text": "Rawnak ara chowdhuri is our department head of computer science at Mymensing Engineering college.",
            "document_name": "handbook.txt",
            "page_number": 1,
            "chunk_id": "chunk-1",
            "similarity_score": 0.5,
        }
    ]

    # Generation is extractive: the exact source sentence is returned verbatim
    # (no LLM paraphrase, expansion, or polish can alter it).
    result = generate_answer("Who is Rawnak Ara?", chunks)
    assert result == "Rawnak ara chowdhuri is our department head of computer science at Mymensing Engineering college."


def test_generate_answer_ignores_unrelated_chunks(monkeypatch):
    """Unrelated retrieved chunks must never be merged into the answer."""
    chunks = [
        {
            "text": "Rawnak ara chowdhuri is our department head of computer science at Mymensing Engineering college.",
            "document_name": "handbook.txt",
            "page_number": 1,
            "chunk_id": "chunk-1",
            "similarity_score": 0.5,
        },
        {
            "text": "Divide & Conquer. Greedy Algorithms. Dynamic Programming.",
            "document_name": "Semester_Plan_CSE_4.pdf",
            "page_number": 3,
            "chunk_id": "chunk-2",
            "similarity_score": 0.4,
        },
    ]
    result = generate_answer("Who is Rawnak Ara?", chunks)
    assert result == "Rawnak ara chowdhuri is our department head of computer science at Mymensing Engineering college."
    assert "Divide" not in result
    assert "Greedy" not in result
    assert "algorithm" not in result.lower()


def test_generate_answer_abstains_on_unsupported_aspect(monkeypatch):
    chunks = [
        {
            "text": "Rawnak Ara is the department head of Computer Science.",
            "document_name": "handbook.txt",
            "page_number": 1,
            "chunk_id": "chunk-1",
            "similarity_score": 0.5,
        }
    ]
    # The source says nothing about research: HalluFix must abstain, not guess.
    assert generate_answer("What research does Rawnak Ara conduct?", chunks) == INSUFFICIENT_MESSAGE
    assert generate_answer("What algorithms does Rawnak Ara specialize in?", chunks) == INSUFFICIENT_MESSAGE


# ---------------------------------------------------------------------------
# Verification (logical support)
# ---------------------------------------------------------------------------

def test_verify_answer_accepts_logically_supported_paraphrase(monkeypatch):
    chunks = [
        {
            "text": "HalluFlow aims to mitigate AI hallucinations through RAG.",
            "document_name": "d.pdf",
            "page_number": 1,
            "chunk_id": "chunk-1",
        }
    ]

    def fake_chat(messages, temperature=0.0, json_mode=True):
        return '{"supported": true, "confidence": 0.9, "reason": "paraphrase of evidence"}'

    monkeypatch.setattr("backend.verifier.chat", fake_chat)
    answer, verification = verify_answer("HalluFlow is designed to reduce hallucination.", chunks)
    assert verification[0]["supported"] is True


def test_verification_summary_reports_counts():
    verification = [
        {"supported": True, "confidence": 1.0},
        {"supported": False, "confidence": 0.0},
    ]
    summary = verification_summary(verification)
    assert summary["supported_claims"] == 1
    assert summary["unsupported_claims"] == 1


# ---------------------------------------------------------------------------
# Hybrid RAG payload (response format)
# ---------------------------------------------------------------------------

def test_hybrid_rag_payload_has_file_page_and_verification_summary(monkeypatch):
    chunks = [
        {
            "document_name": "HalluFlow.pdf",
            "page_number": 27,
            "chunk_id": "chunk-1",
            "text": "HalluFlow improves accuracy and scalability.",
            "similarity_score": 0.7,
        }
    ]

    def fake_generate(question, chunks):
        return "HalluFlow improves accuracy and scalability."

    def fake_verify(answer, chunks):
        return answer, [
            {"supported": True, "confidence": 0.9, "reason": "ok"},
            {"supported": False, "confidence": 0.2, "reason": "x"},
        ]

    with patch("backend.hybrid.generate_answer", fake_generate), patch("backend.hybrid.verify_answer", fake_verify):
        payload = hybrid._build_rag_payload("What is HalluFlow?", chunks, 0.0, 0.8, "reason here")

    assert payload["mode"] == "RAG"
    assert payload["sources"][0]["file"] == "HalluFlow.pdf"
    assert payload["sources"][0]["page"] == 27
    assert payload["verification_summary"]["supported_claims"] == 1
    assert payload["verification_summary"]["unsupported_claims"] == 1