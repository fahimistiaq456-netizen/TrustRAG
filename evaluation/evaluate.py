"""Phase 3 — Multi-domain benchmarking runner.

Supports independent domains under ``evaluation/datasets/<domain>/`` where each
domain contains ``documents/``, ``questions.json`` and ``metadata.json``.

Usage:
    python -m evaluation.evaluate --domain university
    python -m evaluation.evaluate --all
    python -m evaluation.evaluate --list
    python -m evaluation.evaluate --offline --all
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import requests

from . import metrics

ROOT = Path(__file__).resolve().parent
DATASETS_DIR = ROOT / "datasets"
RESULTS_DIR = ROOT / "results"
DEFAULT_API = "http://localhost:8000/ask"

DOMAINS = ("university", "healthcare", "technology", "law", "finance")


# ---------------------------------------------------------------------------
# Dataset loading
# ---------------------------------------------------------------------------
def available_domains() -> list[str]:
    if not DATASETS_DIR.exists():
        return []
    return sorted(
        d.name for d in DATASETS_DIR.iterdir()
        if d.is_dir() and (d / "questions.json").exists()
    )


def load_domain(domain: str) -> dict:
    d = DATASETS_DIR / domain
    if not (d / "questions.json").exists():
        raise FileNotFoundError(f"No dataset for domain: {domain}")
    questions = json.loads((d / "questions.json").read_text(encoding="utf-8"))
    metadata = json.loads((d / "metadata.json").read_text(encoding="utf-8")) if (d / "metadata.json").exists() else {}
    documents = sorted(p.name for p in (d / "documents").glob("*") if p.suffix.lower() in (".txt", ".md", ".pdf"))
    return {"domain": domain, "questions": questions, "metadata": metadata, "documents": documents}


def _base_record(item: dict, domain: str) -> dict:
    return {
        "id": item.get("id", item.get("question", "")),
        "domain": domain,
        "expected_type": item.get("expected_type", item.get("category", "answerable")),
        "reference_answer": item.get("reference_answer", ""),
    }


def evaluate_question(item: dict, domain: str, response: dict | None) -> dict:
    """One row of metrics for a single question.

    Fields requiring a live API response are None when ``response`` is None so
    offline runs report N/A for them.
    """
    base = _base_record(item, domain)
    if response is None:
        return {**base, "abstained": None, "abstention_accurate": None,
                "answer_correct": None, "unsupported_claims": None,
                "recall@5": None, "precision@5": None, "mrr": None}

    expected_sources = [str(s) for s in item.get("expected_sources", [])]
    retrieved = [str(s.get("document_name") or s.get("file") or "") for s in response.get("sources", [])]
    verification = response.get("verification", [])
    unsupported = sum(1 for v in verification if not v.get("supported")) if verification else None

    return {
        **base,
        "abstained": response.get("abstained"),
        "abstention_accurate": metrics.abstention_accurate(base["expected_type"], bool(response.get("abstained"))),
        "answer_correct": metrics.reference_match(response.get("answer", ""), base["reference_answer"]) if base["reference_answer"] else None,
        "unsupported_claims": unsupported,
        "recall@5": metrics.recall_at_k(expected_sources, retrieved, 5),
        "precision@5": metrics.precision_at_k(expected_sources, retrieved, 5),
        "mrr": metrics.mrr(expected_sources, retrieved),
    }


def run(api_url: str = DEFAULT_API, domains: list[str] | None = None, offline: bool = False) -> dict:
    """Run the benchmark over selected domains and write results + report."""
    targets = [d for d in (domains or available_domains()) if d in DOMAINS]
    datasets = [load_domain(d) for d in targets]
    records: list[dict] = []

    for dataset in datasets:
        for item in dataset["questions"]:
            response = None
            if not offline:
                try:
                    resp = requests.post(api_url, json={"question": item["question"]}, timeout=120)
                    response = resp.json() if resp.status_code == 200 else None
                except requests.RequestException:
                    response = None
            rec = evaluate_question(item, dataset["domain"], response)
            rec["system"] = "hallufix_rag"
            records.append(rec)

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    aggregates = {d: aggregate_records([r for r in records if r["domain"] == d]) for d in DOMAINS}
    aggregates["all"] = aggregate_records(records)
    result = {"records": records, "aggregates": aggregates}
    (RESULTS_DIR / "results.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    _write_markdown_report(result)
    return result


def aggregate_records(records: list[dict]) -> dict:
    return metrics.aggregate(records)


def _write_markdown_report(result: dict) -> None:
    lines = ["# Hallufix Multi-Domain Evaluation Report", ""]
    for domain, agg in result["aggregates"].items():
        lines.append(f"## {domain}")
        lines.append(f"- n: {agg['n']}")
        lines.append(f"- Abstention accuracy: {agg['abstention_accuracy']}")
        lines.append(f"- Answer correctness: {agg['answer_correctness']}")
        lines.append(f"- Unsupported-claim rate: {agg['unsupported_claim_rate']}")
        lines.append(f"- Mean MRR: {agg['mean_mrr']}")
        lines.append("")
    (RESULTS_DIR / "report.md").write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the Hallufix multi-domain evaluation.")
    parser.add_argument("--domain", default=None, help="A single domain to evaluate.")
    parser.add_argument("--all", action="store_true", help="Evaluate every available domain.")
    parser.add_argument("--list", action="store_true", help="List available datasets and exit.")
    parser.add_argument("--offline", action="store_true", help="Do not call the API; compute only offline metrics.")
    parser.add_argument("--api-url", default=DEFAULT_API, help="Hallufix /ask endpoint.")
    args = parser.parse_args()

    if args.list:
        print("\n".join(available_domains()) or "(no datasets yet)")
        raise SystemExit(0)

    domains = [args.domain] if args.domain else (list(DOMAINS) if args.all else None)
    print(f"Datasets found: {available_domains()}")
    print(f"Evaluating: {domains or available_domains()} {'(offline)' if args.offline else ''}")
    run(api_url=args.api_url, domains=domains, offline=args.offline)
    print(f"Results -> {RESULTS_DIR / 'results.json'} and {RESULTS_DIR / 'report.md'}")