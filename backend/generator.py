"""Strict evidence-first answer generation.

HalluFix's generation philosophy is: retrieve -> select the exact, relevant
source sentence -> return it verbatim.

The answer is a *real sentence from the retrieved source*, never an LLM
paraphrase, expansion, or polish. No facts are added, inferred, extrapolated,
or combined, and no unrelated retrieved chunks are merged into the answer.

This replaces the previous "natural generation" pipeline (LLM paraphrase +
expansion + stylistic polish) which produced polished-but-unsupported answers.
"""
from __future__ import annotations

import re

from .response_formatter import format_answer
from .retriever import source_list

INSUFFICIENT_MESSAGE = "Insufficient information available in the university handbook."

# Question/stop words ignored when matching source sentences (they appear in
# nearly every sentence, so they are not useful discriminators).
_STOP_WORDS = {
    "what", "which", "where", "when", "who", "how", "why", "is", "are", "was",
    "were", "does", "do", "did", "the", "a", "an", "of", "to", "for", "in",
    "on", "and", "or", "with", "about", "at", "by", "from", "that", "this",
    "it", "its", "mr", "mrs", "ms", "sir", "madam", "called", "named", "tell",
    "me", "know", "please", "can", "could", "you", "his", "her", "their",
    "department", "head", "role", "position", "student",
}

# Aspect keywords that target a *specific* sub-fact which lives *outside* a
# person/entity's identifying sentence (maintained separately on purpose).
# If the question asks about one of these and the selected source sentence does
# not mention that aspect, HalluFix abstains instead of guessing.
_ASPECT_KEYWORDS = {
    "research", "researches", "researcher", "salary", "paid", "earns",
    "specialize", "specializes", "specialty", "expertise",
    "qualification", "qualifications", "degree", "degrees", "age", "born",
    "birthday", "phone", "email", "address", "achievement", "achievements",
    "award", "awards", "oversee", "oversees", "accommodation",
    "accommodations", "accessibility", "disability", "responsibilities",
    "responsibility", "teaches", "teach", "teaching", "publications",
    "published", "papers", "image", "imaging", "processing", "interests",
}


def question_terms(question: str) -> set[str]:
    """Extract the meaningful, stop-word-filtered terms from a question."""
    return {
        token
        for token in re.findall(r"[a-z0-9]+", question.lower())
        if len(token) > 2 and token not in _STOP_WORDS
    }


def candidate_sentences(chunks: list[dict[str, object]]) -> list[tuple[str, float]]:
    """Collect de-duplicated, complete (sentence, similarity) pairs.

    Only proper sentences are considered: each must end with sentence-ending
    punctuation ('.', '!', '?'), which drops headings, list fragments, and
    partial lines so they are never returned as answers.
    """
    seen: set[str] = set()
    result: list[tuple[str, float]] = []
    for chunk in chunks:
        for sentence in re.split(r"(?<=[.!?])\s+", str(chunk["text"])):
            sentence = sentence.strip()
            if not sentence or not sentence[-1] in ".!?":
                continue
            key = re.sub(r"\s+", " ", sentence.lower())
            if key in seen:
                continue
            seen.add(key)
            result.append((sentence, float(chunk.get("similarity_score", 0.0))))
    return result


def select_relevant_sentences(
    question: str, chunks: list[dict[str, object]]
) -> list[str]:
    """Return the single source sentence that best answers the question.

    Ranking is by overlap of question terms with the sentence's words, with
    similarity as a tie-break. Only one best sentence is returned so that
    unrelated retrieved chunks are never merged into the answer.
    """
    terms = question_terms(question)
    if not terms:
        return []

    ranked: list[tuple[int, float, str]] = []
    for sentence, similarity in candidate_sentences(chunks):
        words = set(re.findall(r"[a-z0-9]+", sentence.lower()))
        overlap = len(terms & words)
        if overlap == 0:
            continue
        ranked.append((overlap, similarity, sentence))

    if not ranked:
        return []
    ranked.sort(key=lambda item: (item[0], item[1]), reverse=True)
    best_overlap = ranked[0][0]
    # If there is a genuine tie on both overlap and similarity, prefer the
    # shorter sentence (closer to a concise definition). Single best only.
    ties = [r[2] for r in ranked if r[0] == best_overlap]
    best = min(ties, key=lambda s: len(s.split()))
    return [best]


def _aspect_is_supported(question: str, sentence: str) -> bool:
    """Abstain when the question targets a narrow aspect the sentence omits.

    e.g. "What research does Rawnak Ara conduct?" -> the identifying sentence
    does not mention research, so we cannot answer that aspect.
    """
    question_tokens = set(re.findall(r"[a-z0-9]+", question.lower()))
    asked_aspects = {a for a in _ASPECT_KEYWORDS if a in question_tokens}
    if not asked_aspects:
        # No specific sub-fact requested -> an identifying sentence is a valid
        # answer (e.g. "What is X's role?" is answered by the role sentence).
        return True
    sentence_lower = sentence.lower()
    return all(aspect in sentence_lower for aspect in asked_aspects)


def generate_answer(question: str, chunks: list[dict[str, object]]) -> str:
    """Return the verbatim source sentence that answers the question.

    If no source sentence directly answers the question - or the question asks
    for an aspect the source does not state - abstain instead of guessing.
    """
    if not chunks:
        return INSUFFICIENT_MESSAGE

    selected = select_relevant_sentences(question, chunks)
    if not selected:
        return INSUFFICIENT_MESSAGE

    sentence = selected[0]
    if not _aspect_is_supported(question, sentence):
        return INSUFFICIENT_MESSAGE

    cleaned = format_answer(question, sentence)
    return cleaned or INSUFFICIENT_MESSAGE


def generate_answer_with_sources(question: str, chunks: list[dict[str, object]]) -> dict[str, object]:
    """Verbatim source answer plus a structured citation block (hybrid RAG output)."""
    return {"answer": generate_answer(question, chunks), "sources": source_list(chunks)}
