"""Top-k retrieval and human-readable provenance citations."""
from __future__ import annotations
import re
from .vectorstore import LocalVectorStore


def retrieve(store: LocalVectorStore, question: str, k: int = 10) -> list[dict[str, object]]:
    # Retrieve more chunks to improve coverage for specific queries
    all_chunks = store.search(question, k=k)
    # Filter out very low similarity chunks (< 0.1) but keep more candidates
    return [c for c in all_chunks if float(c["similarity_score"]) >= 0.1]


def citation(chunk: dict[str, object]) -> str:
    page = chunk.get("page_number")
    return f"{chunk['document_name']}" + (f", p. {page}" if page else "") + f" ({chunk['chunk_id']})"


def evidence_text(chunks: list[dict[str, object]]) -> str:
    return "\n\n".join(f"[{citation(c)}]\n{c['text']}" for c in chunks)


def source_list(chunks: list[dict[str, object]]) -> list[dict[str, object]]:
    """Structured source metadata for citation blocks in hybrid answers."""
    return [
        {
            "document_name": chunk["document_name"],
            "page_number": chunk.get("page_number"),
            "chunk_id": chunk["chunk_id"],
            "citation": citation(chunk),
        }
        for chunk in chunks
    ]


def best_source_sentence(question: str, chunks: list[dict[str, object]]) -> str | None:
    """Return the strongest verbatim source sentence as a safe final fallback.

    Compact local models sometimes add plausible wording not present in the
    source. This function never generates text: it selects a source sentence
    whose meaningful words overlap with the question.
    """
    stop_words = {"what", "which", "where", "when", "who", "how", "many", "much", "does", "do", "is", "are", "the", "a", "an", "of", "to", "for", "in", "on", "and", "or", "with", "about", "required"}
    terms = {word for word in re.findall(r"[a-z0-9]+", question.lower()) if len(word) > 2 and word not in stop_words}
    if not terms:
        return None
    candidates: list[tuple[int, float, str]] = []
    for chunk in chunks:
        for sentence in re.split(r"(?<=[.!?])\s+", str(chunk["text"])):
            clean = sentence.strip()
            words = set(re.findall(r"[a-z0-9]+", clean.lower()))
            overlap = len(terms & words)
            if overlap:
                candidates.append((overlap, float(chunk["similarity_score"]), clean))
    if not candidates:
        return None
    overlap, _, sentence = max(candidates, key=lambda item: (item[0], item[1], len(item[2])))
    # More lenient: one matching term (including names) is enough, 
    # but prefer longer matches and higher similarity
    return sentence if overlap >= 1 else None
