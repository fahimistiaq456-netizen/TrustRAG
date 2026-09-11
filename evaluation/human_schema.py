"""Phase 5 — Human evaluation schema and validator.

An evaluator scores a Hallufix answer on a fixed rubric. Each evaluation item
carries the inputs an evaluator needs (question, system answer, reference,
sources, claims) plus normalised integer rubric scores.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Literal

# Rubric dimensions (1..5 scale unless stated).
DIMENSIONS = ("correctness", "groundedness", "citation_quality", "completeness", "overall")
SEVERITY_RANGE = (0, 3)  # hallucination severity 0..3
SCORE_RANGE = (1, 5)

DecisionValue = Literal["accept", "reject", "needs review"]


@dataclass(frozen=True)
class HumanEvaluation:
    evaluation_id: str
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
    evaluator: str = "anonymous"
    domain: str = ""
    system: str = ""

    def validate(self) -> list[str]:
        """Return a list of validation errors (empty when valid)."""
        errors: list[str] = []
        for dim in ("correctness", "groundedness", "citation_quality", "completeness", "overall"):
            value = getattr(self, dim)
            if value < SCORE_RANGE[0] or value > SCORE_RANGE[1]:
                errors.append(f"{dim} must be in {SCORE_RANGE}")
        if not (SEVERITY_RANGE[0] <= self.hallucination_severity <= SEVERITY_RANGE[1]):
            errors.append(f"hallucination_severity must be in {SEVERITY_RANGE}")
        if self.decision not in ("accept", "reject", "needs review"):
            errors.append("decision must be accept/reject/needs review")
        return errors

    @property
    def valid(self) -> bool:
        return not self.validate()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def required_fields() -> list[str]:
    return list(("question", "system_answer",))