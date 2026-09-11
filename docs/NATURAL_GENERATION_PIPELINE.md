# HalluFix Strict Source-Grounded Generation Pipeline

Documentation of HalluFix's answer-generation philosophy:

> **Retrieve evidence → select the exact, relevant source sentence → return it verbatim.**
> No facts are added, inferred, extrapolated, combined, or polished into new facts.

HalluFix is a **strict evidence-based information retrieval system**, not an assistant
that tries to make every answer longer or more natural-sounding.

## 1. The problem this fixes

The previous "natural generation" pipeline asked a compact local model to:
- paraphrase the evidence into "natural human language",
- combine related facts into a coherent explanation,
- polish the answer with a second formatter LLM pass.

That produced answers that *sounded* good but were frequently wrong:

```text
Q: Who is Rawnak Ara?
A: In addition to her administrative role, Rawnak Ara has expertise in algorithms
   such as Divide & Conquer, Greedy Algorithms, and Dynamic Programming.   <- INVENTED
```

The algorithm names came from an unrelated course-syllabus chunk. The model merged
unrelated retrieval results and inferred expertise the source never stated.

## 2. The rule

**If the evidence does not explicitly support the claim, HalluFix must not say it.**

Every factual statement in the final answer is directly supported by the retrieved
evidence, and the answer is a relevant source sentence verbatim — never an LLM
expansion of it.

## 3. Pipeline

```
User Question
      |
Retriever (FAISS + optional graph + optional reranking)
      |
Retrieved Chunks
      |
Strict Extractive Generator (backend/generator.py)
      |   selects the single most relevant verbatim source sentence
      |   (question-term overlap ranking; aspect-gate abstention)
      |
Verification (backend/verifier.py)
      |   deterministic exact match -> NLI -> strict LLM judge
      |   unsupported claims are REMOVED, never returned
      |
Presentation Only (backend/response_formatter.py)
      |   whitespace/punctuation cleanup; NEVER adds facts
      |
Final Answer + Sources + Citations
```

## 4. Strict extractive generator (backend/generator.py)

`generate_answer(question, chunks)` no longer calls the language model at all.

1. **Collect candidates**: every complete sentence (ending in `.`, `!`, `?`) from
   the retrieved chunks, de-duplicated.
2. **Rank by relevance**: count how many meaningful question terms appear in each
   sentence (stop-words like *what/who/is/the/department/head/role* are ignored).
3. **Return ONE best sentence** (tie-break: shorter sentence) — unrelated chunks are
   never merged, because only a single best sentence is returned.
4. **Aspect gate**: if the question targets a specific sub-fact the source does not
   state (research, specialization, qualifications, accessibility, ...), HalluFix
   abstains instead of guessing.

For:

```text
Source:  "Rawnak ara chowdhuri is our department head of computer science at
          Mymensing Engineering college."
Q: Who is Rawnak Ara?
A: Rawnak ara chowdhuri is our department head of computer science at Mymensing
   Engineering college.
```

And:

```text
Q: What research does Rawnak Ara conduct?
A: Insufficient information available in the university handbook.
```

(no sentence in the source mentions Rawnak Ara's research → abstention).

## 5. Context compression is extractive (backend/context_processor.py)

`summarize_evidence` no longer runs an LLM paraphrase. Context compression is
**extractive only**: the original sentences are joined verbatim. An LLM
paraphrasing pass can introduce unsupported information, so it is never used.

## 6. The formatter is presentation-only (backend/response_formatter.py)

`format_answer` performs **only lossless cleanup**:
- whitespace collapse,
- spacing before sentence-ending punctuation,
- removal of embedded citation / metadata keys.

It NEVER: adds facts, adds explanations, adds background, expands the answer,
creates biographies, introduces expertise, or infers relationships.
The previous LLM "polish" pass was removed entirely.

## 7. Verification verifies only the answer claims (backend/verifier.py)

1. The generated answer is split into its own claims (nothing is invented).
2. **Deterministic fast path**: a normalized verbatim containment check accepts
   real source sentences (even with stop-words in the middle).
3. **NLI** (optional): `ENTAILMENT / NEUTRAL / CONTRADICTION` classification.
4. **LLM judge** (fallback): strict — a claim is SUPPORTED only when *every fact*
   in it appears explicitly in the evidence. "Reasonably inferred" is NOT enough.

Unsupported sentences are **removed** from the final answer. If nothing remains:

```text
Insufficient information available in the university handbook.
```

Correct verification output for the Rawnak question is exactly ONE claim:

```json
{
  "claim": "Rawnak ara chowdhuri is our department head of computer science at Mymensing Engineering college.",
  "result": "ENTAILMENT",
  "confidence": "high",
  "evidence": "Rawnak ara chowdhuri is our department head of computer science at Mymensing Engineering college."
}
```

Nothing more — no invented claims about accessibility, algorithms, or research.

## 8. Hybrid routing obeys the same boundary (backend/hybrid.py)

`/chat/hybrid` decides with the **strict generator**, not the similarity score:
- source contains a verbatim answer → **RAG** (grounded source sentence),
- source covers the topic but not the requested aspect → **ABSTAIN**,
- source does not cover the topic → **LLM** (general knowledge).

A low similarity score never routes an entity question to the local model, and a
high similarity score never grants the model permission to repeat everything in a
document.

## 9. Example behaviors

```text
User: Who is Rawnak Ara?
HalluFix: Rawnak ara chowdhuri is our department head of computer science at
          Mymensing Engineering college.

User: Who is Sojibul Islam Rana?
HalluFix: Sojibul Islam rana is a student at Mymensing Engineering college of CSE
          department.

User: What algorithms does Rawnak Ara specialize in?
HalluFix: Insufficient information available in the university handbook.
```

## 10. Testing

`tests/test_natural_generation.py` and `tests/test_hybrid.py` cover:
- verbatim source-sentence generation (no LLM call),
- ignoring unrelated chunks (no cross-document contamination),
- aspect-gate abstention for unsupported questions,
- extractive context compression,
- deterministic verification of verbatim answers,
- strict hybrid routing (low-similarity entity questions still RAG).

Run everything with:

```bash
python -m pytest tests/
```

## 11. Design principle

HalluFix prefers **short + correct** over **long + informative-looking**.

Less information + higher evidence support = better answer.