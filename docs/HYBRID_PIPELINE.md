# Hallufix Hybrid Intelligence Pipeline

## 1. Problem with the previous pipeline

The hybrid tab originally used a judge-driven flow:

```
User Question
      |
Local LLM
      |
LLM judge compares the answer to the evidence
      |
If the judge dislikes the answer
      |
RAG fallback
```

In practice the judge is itself a compact local model and often decided that an
empty-but-polite answer like *"I am not familiar with this person..."* was
acceptable — even when the user's own source library contained the answer. The
source was never consulted, so questions such as *"Who is Asifur?"* (present in
the handbook) returned the local model's refusal.

**Example of the failure mode:**

> Question: "Who is Rawnak Ara Chowdhury?"
>
> Local model: "I am not familiar with this person."
>
> Source library: "Rawnak Ara Chowdhury is our Department Head of Computer
> Science at Mymensing Engineering College."
>
> Old result: the unhelpful local answer is kept.

## 2. New hybrid architecture (source-first)

```
                User Query
                    |
                    |
             Retrieve Top-k Documents
                    |
            ------------------------
            |                      |
     Evidence strong        Evidence weak /
     (confidence >=          no evidence
       threshold)
            |                      |
   RAG answer from source   Local LLM answer
   (generate + verify)            |
            |                    done
   Verification layer
            |
   Citation + Evidence
```

The ordering is the important change: **retrieval runs first**, and the decision
is based on the evidence itself rather than on a fallible LLM judge. If the
source library contains a verbatim sentence that answers the question, we answer
from the source. If the source covers the topic but not the requested aspect, we
abstain. Only when the source does not cover the topic does the local model
answer.

## 3. Data flow

1. `retriever.retrieve(store, question)` — FAISS cosine-similarity top-k with
   chunk metadata (document name, page, chunk id, similarity score).
2. `generator.generate_answer(question, chunks)` — the **strict extractive
   generator** returns a verbatim source sentence that actually answers the
   question, or indicates that the source cannot answer it. Evidence
   confidence (average top-3 similarity) is kept for diagnostics only; it never
   routes an entity question to the local model.
3. Source answers (`_build_rag_payload`):
   - the extractive answer is verified (`verifier.verify_answer`),
   - if verification rejects generated wording, `best_source_sentence` falls
     back to a verbatim source sentence;
   - `mode="RAG"` with full citations.
4. Source covers the topic but lacks the asked information (e.g. "What research
   does Rawnak Ara conduct?") → abstain (`mode="ABSTAIN"`).
5. Source does not cover the topic at all → the local model answers
   (`mode="LLM"`).
6. Every decision is appended to `logs/hybrid_decisions.json`.

## 4. Decision algorithm

```python
source_answer = generate_answer(question, chunks)   # strict extractive
if source_answer is a verbatim source sentence:
    use_rag_answer()          # verify + cite; verbatim fallback
elif the source recognises the question topic:
    abstain()                 # do not let the local model guess
elif local model is available:
    use_llm_answer()          # general knowledge, no sources
else:
    abstain()
```

## 5. Why retrieval happens BEFORE the switch

Routing on the evidence removes the failure mode of the previous design: a local
model that refuses politely can never veto a source answer, because the source
threshold is evaluated first. Retrieval must happen before the switch so the
decision is grounded in the documents rather than in the model's mood.

## 6. Example

| Step | Content |
| --- | --- |
| Input | `Who is Asifur from Mymensing Engineering College?` |
| Retriever | Found matching chunk (top similarity ~0.58). |
| Gate | Evidence confidence ≥ threshold → source answer. |
| Final | `Asifur is a sweet boy from Muktijuddha Hall.` |
| Sources | `university_handbook.pdf, p. 1 (chunk-13)` |

## 7. Advantages

- **Answers always come from the source when the source contains the answer** —
  no more LLM refusals overriding real evidence.
- Reduces hallucination: source answers are grounded and sentence-verified.
- Preserves natural LLM answers: general-knowledge questions not in the sources
  are still answered by the local model.
- Provides citations and verification on every source answer.
- Transparent audit trail: every routing decision is logged.

## 8. Limitations

- A weak index match means the source gate cannot help: retrieval quality
  bounds the answer quality.
- The compact local verifier can occasionally reject even good wording; the
  verbatim source-sentence fallback covers that case.
- The gate relies on `similarity_score`; threshold calibration may be needed for
  new source libraries.

## 9. Module layout

```text
backend/
├── hybrid.py               # source-first orchestration: retrieve -> gate -> RAG/LLM
├── hybrid_evaluator.py     # optional LLM-judge evaluator (kept, not on critical path)
├── decision_engine.py      # legacy judge-based decision helper (kept, not on critical path)
├── generator.py            # grounded RAG generation
├── retriever.py            # top-k retrieval + source metadata
└── verifier.py             # sentence-level claim verification
```

## 10. Migration notes

- `POST /chat/hybrid` wraps `hybrid.run_hybrid`, which is now source-first.
- The response payload is unchanged: `mode`, `answer`, `confidence`, `sources`,
  `verification`, `reason`, `stats`.
- `logs/hybrid_decisions.json` records `decision` (LLM/RAG) and `reason` for
  every hybrid query.
- The LLM-judge modules (`hybrid_evaluator`, `decision_engine`) remain in the
  codebase and are tested, but no longer drive the critical routing path.