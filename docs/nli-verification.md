# NLI Verification

## What it does
Adds a dedicated Natural-Language-Inference (NLI) model to the claim verifier so each
generated sentence is classified against the retrieved evidence as:

```
ENTAILMENT | NEUTRAL | CONTRADICTION
```

with a model confidence. The API response exposes, per claim: `claim`, `label`,
`confidence`, `evidence`, `method` ("nli"), plus a `verification` / `verification_summary`
block. A claim is **supported** when the NLI label is `ENTAILMENT` **and** the confidence
clears `HALLUFIX_NLI_ENTAILMENT_THRESHOLD`.

## Why it exists
The original verifier combined a deterministic exact-phrase/number matcher with an LLM
"logical-support" judge. That is useful but is not a *dedicated* entailment system.
A cross-encoder NLI model directly models the `claim → evidence` relation, giving a
calibrated, deterministic-at-inference label that does not depend on prompt variance.

## Pipeline (extended, not replaced)
```
claim → deterministic fast-path
      → NLI model (when HALLUFIX_NLI_ENABLED=true and reachable)
      → LLM verification fallback (when NLI off / unavailable / returns None)
```
`backend/verifier.py` runs the deterministic path first; if it does not short-circuit, it
calls the NLI stage (`backend/nli.py`); if NLI is disabled or returns ``None`` (model
unavailable), it falls back to the existing LLM judge. Nothing is lost when NLI is off.

## Architecture
- `backend/nli.py`:
  - Lazy thread-safe singleton loading (like the reranker) — never at import time.
  - `classify(claim, evidence) -> NLIResult | None` (None when disabled/unavailable).
  - Maps model logits to the configured label order `[contradiction, entailment, neutral]`
    (default `cross-encoder/nli-MiniLM2-L6-H768`).
  - `threshold(label)` returns the configurable entailment / contradiction thresholds.
- `backend/verifier.py::_judge_by_nli` bridges NLI results into the existing
  `VerificationResult` shape and applies the threshold.

## Configuration (`backend/config.py`, `.env`)
| Variable | Default | Meaning |
|---|---|---|
| `HALLUFIX_NLI_ENABLED` | `false` | Enable the NLI stage |
| `HALLUFIX_NLI_MODEL` | `cross-encoder/nli-MiniLM2-L6-H768` | Sentence-transformers CrossEncoder NLI model |
| `HALLUFIX_NLI_ENTAILMENT_THRESHOLD` | `0.70` | Min entailment confidence to be supported |
| `HALLUFIX_NLI_CONTRADICTION_THRESHOLD` | `0.70` | (reserved) contradiction confidence gate |

The default is a small CPU/M-series friendly cross-encoder that returns `[contradiction,
entailment, neutral]`. Larger options (`cross-encoder/nli-deberta-v3-base`,
`microsoft/deberta-v3-large-mnli`) can be selected via `HALLUFIX_NLI_MODEL`, but require
more RAM/VRAM and slower inference.

## How to run
```bash
pytest tests/test_nli.py   # mocked-model unit + integration tests
```

## Limitations & testing
- Tests mock `load_model` and `predict` so no transformer is downloaded in CI.
- Covered: entailment / negation (contradiction) / neutral mapping, thresholds, graceful
  fallback to `None` when NLI is disabled or the model fails to load, and the
  `verifier._judge_by_nli` integration.
- The NLI label is a model judgment, not a proof: keep the human-review and multi-domain
  evaluation as the ground truth for thesis claims.