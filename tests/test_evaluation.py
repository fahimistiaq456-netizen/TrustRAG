"""Tests for Phases 3 + 5 — multi-domain benchmarking and human evaluation."""
from __future__ import annotations

import json

import pytest

from evaluation import human_metrics, human_store, metrics
from evaluation.evaluate import evaluate_question, load_domain


# ---------------------------------------------------------------------------
# Multi-domain evaluation
# ---------------------------------------------------------------------------
def test_all_domains_present():
    from evaluation.evaluate import available_domains
    assert {"university", "healthcare", "technology", "law", "finance"} <= set(available_domains())


def test_load_domain_layout():
    ds = load_domain("university")
    assert ds["domain"] == "university"
    assert ds["documents"]
    assert all(q.get("expected_type") for q in ds["questions"])
    assert ds["metadata"]["license"]


def test_metrics_helpers():
    relevant = ["a.md", "b.md"]
    retrieved = ["a.md", "c.md", "b.md"]
    assert metrics.recall_at_k(relevant, retrieved, 5) == 1.0
    assert metrics.precision_at_k(relevant, retrieved, 5) == pytest.approx(0.4)
    assert metrics.mrr(relevant, retrieved) == pytest.approx(1.0)


def test_abstention_accuracy():
    assert metrics.abstention_accurate("answerable", False) is True
    assert metrics.abstention_accurate("unanswerable", True) is True
    assert metrics.abstention_accurate("unanswerable", False) is False


def test_evaluate_question_live():
    item = {"expected_type": "answerable", "reference_answer": "120 credits", "expected_sources": ["a.md"], "id": "q1"}
    resp = {"abstained": False, "sources": [{"document_name": "a.md"}], "verification": [{"supported": True}], "answer": "You need 120 credits to graduate."}
    row = evaluate_question(item, "university", resp)
    assert row["abstention_accurate"] is True
    assert row["answer_correct"] is True
    assert row["recall@5"] == 1.0


def test_evaluate_question_offline():
    item = {"expected_type": "answerable", "reference_answer": "", "expected_sources": []}
    row = evaluate_question(item, "university", None)
    assert row["abstention_accurate"] is None
    assert row["mrr"] is None


# ---------------------------------------------------------------------------
# Human evaluation
# ---------------------------------------------------------------------------
def test_human_schema_validation():
    from evaluation.human_schema import HumanEvaluation
    good = HumanEvaluation(evaluation_id="1", question="Q", system_answer="A",
                           correctness=4, groundedness=4, citation_quality=4, completeness=4,
                           hallucination_severity=1, overall=4, decision="accept")
    assert good.valid
    bad = HumanEvaluation(evaluation_id="2", question="Q", system_answer="A",
                          correctness=9, groundedness=4, citation_quality=4, completeness=4,
                          hallucination_severity=1, overall=4, decision="maybe")
    assert [*bad.validate(), "forced"]  # has errors


def test_human_store_add_and_summary(tmp_path, monkeypatch):
    monkeypatch.setattr(human_store, "HUMAN_EVAL_DIR", tmp_path / "human")
    human_store.add_evaluation({
        "question": "What is X?", "system_answer": "X is Y.",
        "correctness": 4, "groundedness": 4, "citation_quality": 4, "completeness": 5,
        "hallucination_severity": 1, "overall": 4, "decision": "accept", "domain": "university",
        "evaluator": "rater1", "item_id": "i-1",
    })
    human_store.add_evaluation({
        "question": "What is X?", "system_answer": "X is Y.",
        "correctness": 4, "groundedness": 3, "citation_quality": 4, "completeness": 4,
        "hallucination_severity": 1, "overall": 4, "decision": "reject", "domain": "university",
        "evaluator": "rater2", "item_id": "i-1",
    })
    records = human_store.all_evaluations()
    assert len(records) == 2
    summary = human_store.summary()
    assert summary["n"] == 2
    assert summary["decisions"]["accept"] == 1 and summary["decisions"]["reject"] == 1
    assert summary["averages"]["overall"] == 4.0


def test_cohen_kappa_two_raters():
    evaluations = [
        {"question": "q1", "evaluator": "a", "decision": "accept"},
        {"question": "q1", "evaluator": "b", "decision": "accept"},
        {"question": "q2", "evaluator": "a", "decision": "reject"},
        {"question": "q2", "evaluator": "b", "decision": "reject"},
    ]
    agreement = human_metrics.inter_rater_agreement(evaluations)
    assert agreement["value"] == 1.0


def test_cohen_kappa_na_without_overlap():
    evaluations = [{"question": "q1", "evaluator": "a", "decision": "accept"}]
    agreement = human_metrics.inter_rater_agreement(evaluations)
    assert agreement["value"] == "N/A"