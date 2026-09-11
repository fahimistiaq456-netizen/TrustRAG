# Cross-Encoder Reranking

## What it does
A cross-encoder reranking stage sits between FAISS candidate retrieval and
context processing:

```
Question → FAISS candidate retrieval → candidate filtering
        → Cross-Encoder rerank → top-N evidence → abstention / context
```

FAISS returns a superset of candidate chunks at roughly ``HALLUFIX_RERANK_CANDIDATES``
(10). The reranker scores each `(question, chunk)` pair jointly and keeps the most
relevant ``HALLUFIX_RERANK_TOP_N`` (5). Each surviving chunk keeps both its original
FAISS ``similarity_score`` and a new ``reranker_score`` so the UI and audit log can
show both signals.

## Why it exists
FAISS with `all-MiniLM-L6-v2` uses cosine similarity between independently embedded
query and passage vectors. That is fast but produces only a coarse relevance order.
A cross-encoder sees the query and passage *together* in one transformer, capturing
token-level interaction and paraphrase/negation relationships that dense retrieval
misses. Reranking therefore typically improves **Recall@K / Precision@K / MRR** for a
fixed budget of grounded context, which directly affects how much correct evidence the
generator and verifier see.

## Architecture
- `backend/reranker.py` — the only module that knows about the cross-encoder model.
  - **Lazy, thread-safe singleton loading** (`_lock` + module globals). The model is
    loaded on the first call that needs it, then reused. Nothing loads at import time.
  - **Graceful degradation**: if the model cannot be loaded/failed earlier, or the
    feature is disabled, the FAISS candidates are returned unchanged with
    ``reranked=False`` so the rest of RAG continues.
  - The retriever never references the reranker; ``api._run_rag`` explicitly composes
    `retrieve → graph_retrieve → rerank_candidates`.

## Configuration (`backend/config.py`, `.env`)
| Variable | Default | Meaning |
|---|---|---|
| `HALLUFIX_RERANKER_ENABLED` | `false` | Enable the stage |
| `HALLUFIX_RERANKER_MODEL` | `cross-encoder/ms-marco-MiniLM-L-6-v2` | sentence-transformers CrossEncoder |
| `HALLUFIX_RERANK_CANDIDATES` | `10` | FAISS candidates considered (candidate K) |
| `HALLUFIX_RERANK_TOP_N` | `5` | Final number of evidence chunks kept (N) |
| `HALLUFIX_RERANK_MIN_SCORE` | `-10.0` | Drop chunks below this reranker score; `-10` disables filtering |

The default `ms-marco-MiniLM-L-6-v2` (≈ 60 MB, ~23M parameters) is small enough for an
M-series Mac / CPU. Swap via `HALLUFIX_RERANKER_MODEL` when bigger models fit.

## How to run / test
```bash
# Unit + mocked-model tests:
pytest tests/test_reranker.py

# Compare FAISS-only vs FAISS+reranking via the multi-domain runner
python -m evaluation.evaluate --all
```

## Testing & limitations
- `tests/test_reranker.py` mocks model scores so no transformer is downloaded in CI.
- Reranking requires one extra model load; first request after enabling it is slower.
- The model is English-centric; domain relevance scoring is a proxy, not a proof.

The retrieval quality improvement is quantified in the multi-domain evaluation report
(`evaluation/results/report.md`), comparing recall/precision/MRR with and without the
stage. Run the benchmarks against Ollama + FAISS to reproduce the comparison.