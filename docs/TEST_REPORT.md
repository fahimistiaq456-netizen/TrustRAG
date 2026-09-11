# Hallufix — Final Test Report

Date: 2026-08-26 · Python 3.11.14 · FastAPI · FAISS · Ollama-optional

## Summary

- **Unit/integration tests:** `pytest -q` → **68 passed, 0 failed** (1 deprecation warning only).
- **Frontend (Next.js):** `npm run lint` clean, `npm run build` successful.
- **Backend startup:** `backend.api` imports; core endpoints smoke-tested via FastAPI `TestClient` all return 200.
- **Evaluation runner:** `python -m evaluation.evaluate --offline --all` runs over all 5 domains and writes `results.json` + `report.md` (offline metrics correctly reported as `N/A`).

## Test inventory (by area)

### Retrieval & abstention (`tests/test_abstention.py`, `tests/test_reranker.py`)
- Abstention threshold gating, LLM-refusal detection.
- Reranking: disabled/empty short-circuit, reorder by cross-encoder score, top-N limit,
  min-score filtering, model-load failure graceful degradation.

### Verification & NLI (`tests/test_nli.py`, `tests/test_natural_generation.py`)
- NLI entailment / contradiction / neutral mapping and thresholds; graceful `None` when
  disabled/unavailable; verifier integration; deterministic + LLM fallback.
- Sentence chunking, dedupe, context preprocessing, verification-summary counts.

### Evaluation (`tests/test_evaluation.py`)
- All 5 domains present; dataset layout; metric helpers (recall/precision/MRR),
  abstention accuracy, live + offline question rows.
- Human evaluation: schema validation, JSONL store, Cohen's kappa (two raters = 1.0) and
  explicit `N/A` with sample size when no overlap.

### Graph (`tests/test_graph.py`)
- Build/load round-trip, node provenance, seed finding from query terms, evidence fusion,
  disabled / missing-graph graceful degradation.

### Auth / RBAC (`tests/test_auth.py`)
- Password hash round-trip, register→login→me, invalid-password rejection, expired and
  tampered tokens rejected, USER denied on admin endpoints, ADMIN allowed, privilege
  escalation blocked.

### Hybrid & generation (`tests/test_hybrid.py`, `tests/test_natural_generation.py`)
- Hybrid mode selection (LLM/RAG/ABSTAIN), evidence strength, verbatim source fallback,
  natural-generation pipeline safety checks.

## Endpoint smoke checks (auth disabled ⇒ dev mode)

```
GET /health                     200
GET /sources                    200
GET /auth/status                200
GET /auth/me                    200
GET /evaluation/domains         200
GET /evaluation/summary         200
GET /human-evaluation/results   200
```

## Enabling optional features

Optional ML/security stages (`HALLUFIX_RERANKER_ENABLED`, `HALLUFIX_NLI_ENABLED`,
`HALLUFIX_GRAPH_ENABLED`, `HALLUFIX_AUTH_ENABLED`) are **off by default** and are
exercise-heavy models (cross-encoder / NLI). Both degrade gracefully: failures leave the
FAISS RAG pipeline running. To validate them live, set the env vars in `.env`, ensure the
models are cached locally, and re-run `pytest` for the relevant module.

## Reproducibility notes

- All model-gated / OpenAI-free tests mock `load_model` / `predict`.
- No test depends on a running Ollama server (live-only paths are guarded or mocked).
- Benchmarks are reproducible via `python -m evaluation.evaluate --all` and human ratings
  via `POST /human-evaluation` → `evaluation/human/evaluations.jsonl`.