"""Phase 5 — Human evaluation metrics and inter-rater agreement.

Computes, from a collection of stored evaluations:

  * average score per rubric dimension
  * per-domain averages
  * per-system averages
  * multi-evaluator agreement (Cohen's kappa when exactly two evaluators rated
    the same items, otherwise an explicit note that agreement is N/A with the
    sample size reported).

The framework is explicitly truthful about sample size: it never over-claims
statistical validity from a handful of ratings.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Iterable

DIMS = ("correctness", "groundedness", "citation_quality", "completeness", "overall")


def _mean(values: list[float]) -> float:
    return round(sum(values) / len(values), 3) if values else 0.0


def average_scores(items: Iterable[dict]) -> dict[str, float]:
    """Average rubric scores (and report sample size ``n``)."""
    items = list(items)
    result: dict[str, float] = {}
    for dim in DIMS:
        result[dim] = _mean([float(i[dim]) for i in items if i.get(dim) is not None])
    result["hallucination_severity"] = _mean([float(i["hallucination_severity"]) for i in items if i.get("hallucination_severity") is not None])
    result["n"] = len(items)
    return result


def _cohen_kappa(decisions_a: dict[str, str], decisions_b: dict[str, str]) -> float:
    """Cohen's kappa for two raters over shared items (categorical decisions)."""
    shared = set(decisions_a) & set(decisions_b)
    if len(shared) < 2:
        return float("nan")
    categories = set(list(decisions_a.values()) + list(decisions_b.values()))
    observed = sum(1 for k in shared if decisions_a[k] == decisions_b[k]) / len(shared)
    expected = 0.0
    for cat in categories:
        pa = sum(1 for k in shared if decisions_a[k] == cat) / len(shared)
        pb = sum(1 for k in shared if decisions_b[k] == cat) / len(shared)
        expected += pa * pb
    denom = 1.0 - expected
    if denom == 0:
        return 1.0
    return round((observed - expected) / denom, 3)


def inter_rater_agreement(evaluations: list[dict]) -> dict[str, object]:
    """Cohen's kappa across evaluators who rated the same items.

    Reports N/A explicitly (with a reason) when agreement is not computable.
    """
    by_item: dict[str, dict[str, str]] = defaultdict(dict)
    for ev in evaluations:
        eid = ev.get("item_id") or ev.get("evaluation_id") or ev.get("question")
        by_item[eid][ev.get("evaluator") or "anonymous"] = ev.get("decision", "")

    n_evaluators = len({e.get("evaluator") for e in evaluations})
    n_items = len(by_item)

    # Extract per-evaluator decision maps over the shared items.
    evaluator_rows: dict[str, dict[str, str]] = defaultdict(dict)
    for item_id, raters in by_item.items():
        for evaluator, decision in raters.items():
            evaluator_rows[evaluator][item_id] = decision

    evaluator_names = list(evaluator_rows)
    if len(evaluator_names) == 2:
        kappa = _cohen_kappa(evaluator_rows[evaluator_names[0]], evaluator_rows[evaluator_names[1]])
        return {
            "metric": "cohen_kappa",
            "evaluators": evaluator_names,
            "value": kappa,
            "n_evaluators": 2,
            "n_items": n_items,
            "explanation": "Two raters shared decisions over the same items."
            if _is_finite(kappa)
            else "Fewer than two shared items; kappa is N/A (sample too small).",
        }

    return {
        "metric": "cohen_kappa",
        "value": "N/A",
        "n_evaluators": n_evaluators,
        "n_items": n_items,
        "explanation": "Agreement requires two evaluators rating the same items; reported sample size is explicit.",
    }


def _is_finite(value: object) -> bool:
    try:
        import math
        return math.isfinite(float(value))
    except (TypeError, ValueError):
        return False


def decisions_summary(evaluations: list[dict]) -> dict[str, int]:
    summary: dict[str, int] = {"accept": 0, "reject": 0, "needs review": 0}
    for ev in evaluations:
        decision = ev.get("decision", "needs review")
        summary[decision] = summary.get(decision, 0) + 1
    return summary


def by_group(evaluations: list[dict], key: str) -> dict[str, dict]:
    """Group evaluations by a field (e.g. ``domain`` / ``system``) and average."""
    groups: dict[str, list[dict]] = defaultdict(list)
    for ev in evaluations:
        groups[ev.get(key, "")].append(ev)
    return {group: average_scores(items) for group, items in groups.items()}