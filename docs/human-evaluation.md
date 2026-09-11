# Human Evaluation Framework

## What it does
Lets human evaluators judge HalluFix answers against a fixed rubric and a reference
answer, stores the ratings, and computes aggregate + inter-rater agreement metrics.
Multiple evaluators can rate the same items.

## Why it exists
Automated metrics (recall, MRR, NLI entailment, token-overlap correctness) are not a
substitute for human judgment of answer usefulness, groundedness and hallucination
severity. The framework gives the thesis a transparent, honest human-signal pipeline.

## Data model (`evaluation/human_schema.py`)
Each record contains the inputs an evaluator needs:
`question`, `system_answer`, `reference_answer`, `sources`, `claims`, plus rubric scores:

| Dimension | Scale |
|---|---|
| Answer correctness | 1–5 |
| Groundedness | 1–5 |
| Citation quality | 1–5 |
| Completeness | 1–5 |
| Hallucination severity | 0–3 |
| Overall usefulness | 1–5 |

Plus a disposition `decision` ∈ `accept | reject | needs review`, `notes`, `evaluator`,
`domain`, `system`, and an `item_id` linking raters on the same item.

## Storage (`evaluation/human_store.py`)
Append-only **JSON Lines** store at `evaluation/human/evaluations.jsonl` (local, easy to
inspect/version — no database needed). `add_evaluation` validates via the schema
(`HumanEvaluation.validate`) before appending.

## Metrics (`evaluation/human_metrics.py`)
- `average_scores(...)` — mean per rubric dimension + `n`.
- `decisions_summary(...)` — accept/reject/needs-review counts.
- `by_group(..., "domain" | "system")` — per-domain / per-system averages.
- `inter_rater_agreement(...)` — **Cohen's kappa** when exactly two evaluators rated the
  same items and ≥2 shared items; otherwise returns `"N/A"` **and always reports the
  explicit sample size** (`n_evaluators`, `n_items`) with an explanation. The framework
  never over-claims statistical validity from a handful of ratings.

## API
- `POST /human-evaluation` — submit a rating (EVALUATOR+; local admin when auth off).
- `GET /human-evaluation/results` — stored evaluations + summary (EVALUATOR+).

## How to run / test
```bash
python -m pip install -r requirements.txt
pytest tests/test_evaluation.py   # human schema, store, kappa, N/A handling
```
A simple local interface can be a Streamlit page or a Next.js view that reads
`GET /human-evaluation/results` and posts to `POST /human-evaluation`.

## Limitations & testing
- Tests cover schema validation, the append store, Cohen's kappa (perfect agreement = 1.0)
  and the explicit `N/A` path when there is no overlap.
- Scientific validity depends on having enough raters/items; the code refuses to pretend
  otherwise and reports the sample size explicitly.