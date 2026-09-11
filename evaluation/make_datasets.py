"""Generate tiny, clearly-synthetic multi-domain benchmark datasets.

Each domain folder includes:
    documents/   - small, handmade markdown documents (public-domain / synthetic)
    questions.json   - answerable / unanswerable / misleading / contradiction / multi-hop
    metadata.json     - model + config provenance for reproducibility

Run once with ``python -m evaluation.make_datasets``. Nothing copyrighted is used.
"""
from __future__ import annotations

import json
from pathlib import Path

BASE = Path(__file__).resolve().parent / "datasets"


def _write_domain(domain: str, documents: dict[str, str], questions: list[dict]) -> None:
    d = BASE / domain
    (d / "documents").mkdir(parents=True, exist_ok=True)
    for name, body in documents.items():
        (d / "documents" / name).write_text(body, encoding="utf-8")
    (d / "questions.json").write_text(json.dumps(questions, indent=2), encoding="utf-8")
    (d / "metadata.json").write_text(json.dumps({
        "domain": domain,
        "description": "Synthetic benchmark dataset for Hallufix.",
        "license": "Public domain (self-authored, synthetic).",
        "embedding_model": "sentence-transformers/all-MiniLM-L6-v2",
    }, indent=2), encoding="utf-8")


def main() -> None:
    _write_domain(
        "university",
        {
            "academic_policy.md": """# Academic Policy
Undergraduate students must complete 120 credit hours to graduate.
A cumulative grade point average (GPA) of at least 2.00 is required.
At least 30 credits must be completed in residence at this university.
Course withdrawal is permitted until the end of week 10 of a semester.
All students must follow the academic integrity code.""",
            "financial_aid.md": """# Financial Aid
Tuition fees are due before the first day of classes each term.
A limited number of merit scholarships are awarded each year.
A financial aid application requires a completed form.""",
        },
        [
            {"id": "uni-001", "domain": "university", "expected_type": "answerable", "question": "What is the graduation GPA cutoff?", "reference_answer": "2.00", "expected_sources": ["academic_policy.md"]},
            {"id": "uni-002", "domain": "university", "expected_type": "answerable", "question": "How many credits are needed to graduate?", "reference_answer": "120", "expected_sources": ["academic_policy.md"]},
            {"id": "uni-003", "domain": "university", "expected_type": "misleading", "question": "Can students withdraw after week 12?", "reference_answer": "No, withdrawal ends within week 10", "expected_sources": ["academic_policy.md"]},
            {"id": "uni-004", "domain": "university", "expected_type": "unanswerable", "question": "What is the football team's win-loss record?", "reference_answer": "", "expected_sources": []},
        ],
    )

    _write_domain(
        "healthcare",
        {
            "first_aid_guide.md": """# First Aid Guide
The recommended daily water intake for a resting adult is about two litres.
A heart attack requires emergency medical attention immediately.
Rest alone is not a treatment for a blocked artery.""",
            "vaccines.md": """# Vaccines
A standard adult dose is administered intramuscularly.
Two booster doses are recommended for the flu season.""",
        },
        [
            {"id": "he-001", "domain": "healthcare", "expected_type": "answerable", "question": "What is the recommended daily water intake?", "reference_answer": "two litres", "expected_sources": ["first_aid_guide.md"]},
            {"id": "he-002", "domain": "healthcare", "expected_type": "misleading", "question": "Is a heart attack treatable with rest alone?", "reference_answer": "No, urgent medical attention", "expected_sources": ["first_aid_guide.md"]},
            {"id": "he-003", "domain": "healthcare", "expected_type": "unanswerable", "question": "What is the price of a flu vaccine?", "reference_answer": "", "expected_sources": []},
        ],
    )

    _write_domain(
        "technology",
        {
            "kubernetes_manual.md": """# Kubernetes Handbook
A pod is the smallest deployable unit in a cluster.
The control plane coordinates scheduling and state.
A node runs containerized workloads.""",
        },
        [
            {"id": "tech-001", "domain": "technology", "expected_type": "answerable", "question": "What is the smallest deployable unit in a cluster?", "reference_answer": "pod", "expected_sources": ["kubernetes_manual.md"]},
            {"id": "tech-002", "domain": "technology", "expected_type": "multi-hop", "question": "Which component coordinates the scheduling of pods?", "reference_answer": "control plane", "expected_sources": ["kubernetes_manual.md"]},
            {"id": "tech-003", "domain": "technology", "expected_type": "unanswerable", "question": "What GPU vendor ships the cluster?", "reference_answer": "", "expected_sources": []},
        ],
    )

    _write_domain(
        "law",
        {
            "civil_procedure.md": """# Civil Procedure Summary
A complaint must be filed within thirty days of the incident.
A court response fee applies to every filing.""",
        },
        [
            {"id": "law-001", "domain": "law", "expected_type": "answerable", "question": "Within how many days must a complaint be filed?", "reference_answer": "thirty days", "expected_sources": ["civil_procedure.md"]},
            {"id": "law-002", "domain": "law", "expected_type": "contradiction", "question": "A complaint can be filed at any time.", "reference_answer": "No, within thirty days", "expected_sources": ["civil_procedure.md"]},
            {"id": "law-003", "domain": "law", "expected_type": "unanswerable", "question": "What is the jury selection cost?", "reference_answer": "", "expected_sources": []},
        ],
    )

    _write_domain(
        "finance",
        {
            "accounting.md": """# Accounting Basics
A company quarterly report includes three statements.
The statements are the income statement, balance sheet and cash flow.""",
            "investment.md": """# Investment Guide
Compound interest is interest calculated on the initial principal, which also
includes all the accumulated interest of previous periods.""",
        },
        [
            {"id": "fin-001", "domain": "finance", "expected_type": "answerable", "question": "How many statements does a quarterly report include?", "reference_answer": "three", "expected_sources": ["accounting.md"]},
            {"id": "fin-002", "domain": "finance", "expected_type": "misleading", "question": "A quarterly report includes five statements.", "reference_answer": "No, three", "expected_sources": ["accounting.md"]},
            {"id": "fin-003", "domain": "finance", "expected_type": "answerable", "question": "What is compound interest calculated on?", "reference_answer": "principal and accumulated interest", "expected_sources": ["investment.md"]},
            {"id": "fin-004", "domain": "finance", "expected_type": "unanswerable", "question": "What is today's exchange rate?", "reference_answer": "", "expected_sources": []},
        ],
    )


if __name__ == "__main__":
    main()
    print("Datasets written under", BASE)