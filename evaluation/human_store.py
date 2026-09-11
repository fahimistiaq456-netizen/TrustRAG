"""Phase 5 — Human evaluation persistence (JSON append store).

Stores human evaluation records in ``evaluation/human/`` as JSON Lines. A
simple append-only store is enough for a local academic project and is easy to
inspect, diff and version — no database required.
"""
from __future__ import annotations

import json
from pathlib import Path

from . import human_metrics
from .human_schema import HumanEvaluation

HUMAN_EVAL_DIR = Path(__file__).resolve().parent / "human"
HUMAN_EVAL_PATH = HUMAN_EVAL_DIR / "evaluations.jsonl"


def _path() -> Path:
    # Resolve from the (possibly monkeypatched) directory at call time so the
    # store is easy to redirect in tests and honours a runtime override.
    return HUMAN_EVAL_DIR / "evaluations.jsonl"


def _ensure() -> Path:
    HUMAN_EVAL_DIR.mkdir(parents=True, exist_ok=True)
    return _path()


def all_evaluations() -> list[dict]:
    path = _ensure()
    if not path.exists():
        return []
    records: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return records


def add_evaluation(ev: dict) -> dict:
    """Validate and append one evaluation record; returns the stored record."""
    model = HumanEvaluation(
        evaluation_id=ev.get("evaluation_id") or ev.get("question", ""),
        question=ev.get("question", ""),
        system_answer=ev.get("system_answer", ""),
        reference_answer=ev.get("reference_answer", ""),
        sources=ev.get("sources"),
        claims=ev.get("claims"),
        correctness=int(ev.get("correctness", 0)),
        groundedness=int(ev.get("groundedness", 0)),
        citation_quality=int(ev.get("citation_quality", 0)),
        completeness=int(ev.get("completeness", 0)),
        hallucination_severity=int(ev.get("hallucination_severity", 0)),
        overall=int(ev.get("overall", 0)),
        decision=ev.get("decision", "needs review"),
        notes=ev.get("notes", ""),
        evaluator=ev.get("evaluator", "anonymous"),
        domain=ev.get("domain", ""),
        system=ev.get("system", ""),
    )
    errors = model.validate()
    if errors:
        raise ValueError("Invalid human evaluation: " + "; ".join(errors))
    path = _ensure()
    record = model.to_dict()
    record["item_id"] = ev.get("item_id", "") or model.evaluation_id
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record) + "\n")
    return record


def summary() -> dict:
    """Aggregate metrics for the evaluation dashboard."""
    records = all_evaluations()
    return {
        "n": len(records),
        "averages": human_metrics.average_scores(records),
        "decisions": human_metrics.decisions_summary(records),
        "by_domain": human_metrics.by_group(records, "domain"),
        "by_system": human_metrics.by_group(records, "system"),
        "agreement": human_metrics.inter_rater_agreement(records),
    }