# Hallufix architecture and thesis contribution

## System architecture

Hallufix implements an evidence-first, local question-answering pipeline with two
comparison modes (normal local conversation and HalluFix RAG) extended with optional
retrieval-quality and verification stages.

```text
Question
   ↓  FAISS candidate retrieval (all-MiniLM-L6-v2, cosine-similarity)
   ↓  optional Graph retrieval (networkx) → evidence fusion
   ↓  optional Cross-Encoder reranking → top-N evidence
   ↓  Strict extractive generator (verbatim source sentence; aspect-gate abstention)
   ↓  Sentence verification: deterministic → optional NLI → strict LLM fallback
   ↓  Presentation-only formatting (never adds facts)
   ↓  Audit log
```

Ingestion accepts multiple PDF and TXT sources, cleans whitespace conservatively, then
creates overlapping sentence-aware chunks (~800 chars, ~150 overlap). Each chunk preserves
document name, page number (for PDFs) and a stable chunk identifier. `all-MiniLM-L6-v2`
runs locally on CPU to embed chunks and queries; a normalized FAISS inner-product index
(`IndexFlatIP`) supplies cosine-similarity retrieval. On `/ingest` the local knowledge
graph is also built (`data/index/graph.json`). Uploaded sources remain in the local
`data/sources/` folder.

Answer generation is strictly extractive: `backend/generator.py` selects the single
most relevant verbatim source sentence for the question (question-term overlap ranking)
and returns it unchanged — no language model paraphrase, expansion, or polish. If the
question targets an aspect the source does not state (research, specialization, ...),
the generator abstains. The verifier then evaluates the answer's own claims against
the evidence, extending a deterministic verbatim/number matcher with an optional
NLI entailment model and a strict LLM judge fallback. Unsupported sentences are
dropped, never returned.

## Optional stages and configuration

All optional stages live in separate modules and degrade gracefully when disabled or when
their model cannot load (the rest of the pipeline continues unchanged):

- **Reranking** — `backend/reranker.py`. `HALLUFIX_RERANKER_ENABLED=false` by default.
- **NLI verification** — `backend/nli.py`, wired into `backend/verifier.py`.
  `HALLUFIX_NLI_ENABLED=false` by default.
- **Graph retrieval** — `backend/graphstore.py` + `backend/graph_retriever.py`.
  `HALLUFIX_GRAPH_ENABLED=false` by default.
- **Authentication / RBAC** — `backend/auth/`. `HALLUFIX_AUTH_ENABLED=false` by default.
- Central settings in `backend/config.py` (read from `.env` / `HALLUFIX_*` vars).

See `docs/reranking.md`, `docs/nli-verification.md`, `docs/graph-retrieval.md`,
`docs/authentication.md`, `docs/multi-domain-evaluation.md`, and `docs/human-evaluation.md`.

## Research contribution

Plain RAG improves factual grounding but does not establish that every generated sentence
is entailed by retrieved context. Hallufix layers several transparent controls:
pre-generation evidence sufficiency (abstention), retrieval-quality (reranking + graph)
and post-generation claim verification (deterministic + NLI + LLM). The audit log stores
the raw answer alongside the final answer, retrieval evidence, per-claim verdicts, and
confidence, enabling a thesis evaluation of both answer quality and safety behaviour.

The multi-domain benchmark (`evaluation/`) measures, per domain (university, healthcare,
technology, law, finance), retrieval recall/precision/MRR, answer correctness, abstention
accuracy and unsupported-claim rates — and allows a head-to-head comparison of baseline
RAG vs RAG+reranking vs RAG+reranking+NLI vs full HalluFix. A human-evaluation framework
(`evaluation/human/`) adds rubric-based ratings and inter-rater agreement with an explicit
sample-size caveat.

## Limitations

- Cosine similarity is a useful but imperfect proxy for evidence sufficiency; threshold
  calibration requires held-out questions.
- NLI and LLM verdicts are model judgments, not formal proof systems.
- PDF extraction quality limits the retrieval corpus.
- The graph entity/keyword extraction is a lightweight offline heuristic, not a semantic
  ontology.
- Live multi-domain comparison requires Ollama running and a built index; offline runs
  report N/A for live-only metrics.

## Future improvements

Calibrate thresholds with validation data; retain source spans rather than whole chunks;
use JSON-schema structured outputs; build out the Next.js evaluation/admin dashboards; and
add more benchmark domains. A stronger study should include multiple corpora, matched
adapters for plain-RAG/LLM-only baselines, and more human evaluators.