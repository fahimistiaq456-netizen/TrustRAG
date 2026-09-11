"""Evaluation routes: dataset info, run, and human-evaluation submission.

Endpoints:
    GET  /evaluation/domains   - list available benchmark datasets
    GET  /evaluation/summary   - aggregated results of the last offline/live run
    POST /human-evaluation     - submit a human evaluation record (EVALUATOR+)
    GET  /human-evaluation/results - stored human evaluations + metrics (EVALUATOR+)

When auth is disabled the dependencies resolve to a local admin, so the same
paths work for local development.
"""
from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from evaluation import (
    evaluate as eval_runner,
    human_store,
)
from .auth.dependencies import require_role
from .auth.models import User

router = APIRouter()


class HumanEvaluationRequest(BaseModel):
    question: str
    system_answer: str
    reference_answer: str = ""
    sources: list[dict] | None = None
    claims: list[dict] | None = None
    correctness: int = 0
    groundedness: int = 0
    citation_quality: int = 0
    completeness: int = 0
    hallucination_severity: int = 0
    overall: int = 0
    decision: str = "needs review"
    notes: str = ""
    domain: str = ""
    system: str = ""
    item_id: str = ""


@router.get("/evaluation/domains")
def evaluation_domains(_: User = Depends(require_role("EVALUATOR"))) -> dict[str, object]:
    return {"domains": eval_runner.available_domains()}


@router.get("/evaluation/summary")
def evaluation_summary(_: User = Depends(require_role("EVALUATOR"))) -> dict[str, object]:
    results_path = eval_runner.RESULTS_DIR / "results.json"
    if not results_path.exists():
        return {"available": False, "note": "No evaluation run found. Run `python -m evaluation.evaluate --all` first."}
    try:
        result = json.loads(results_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"available": False, "note": "Corrupt evaluation result file."}
    return {"available": True, "aggregates": result.get("aggregates", {}), "row_count": len(result.get("records", []))}


@router.post("/evaluation/run")
def evaluation_run(_: User = Depends(require_role("EVALUATOR")), offline: bool = True) -> dict[str, object]:
    """Trigger a benchmark run. Defaults to offline (no live API) for safety."""
    try:
        result = eval_runner.run(offline=offline)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Evaluation failed: {exc}") from exc
    return {"available": True, "aggregates": result.get("aggregates", {}), "row_count": len(result.get("records", []))}


@router.post("/human-evaluation")
def submit_human_evaluation(req: HumanEvaluationRequest, user: User = Depends(require_role("EVALUATOR"))) -> dict[str, object]:
    payload = req.model_dump()
    payload["evaluator"] = (user.username if user.id is not None else "local")
    payload["evaluation_id"] = payload.get("item_id") or f"{req.domain or 'general'}:{req.question[:40]}"
    try:
        stored = human_store.add_evaluation(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"stored": stored["item_id"]}


@router.get("/human-evaluation/results")
def human_evaluation_results(_: User = Depends(require_role("EVALUATOR"))) -> dict[str, object]:
    return human_store.summary()