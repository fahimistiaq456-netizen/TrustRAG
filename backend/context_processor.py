"""Context Preprocessing Layer for RAG answers.

Raw retrieved chunks are noisy: they begin and end mid-sentence, repeat
overlapping text, and contain headings/fragments. This module turns them into
clean, complete sentences. Context compression is extractive only - original
sentences are joined verbatim so no new facts can ever be introduced.

Pipeline:
  chunks -> extract sentences -> merge broken boundaries -> validate -> dedupe
         -> extractive evidence join (no LLM summarization)
"""
from __future__ import annotations

import re

# A sentence is considered valid only when it:
#   - starts with a capital letter (or an opening quote / digit for lists)
#   - ends with '.', '?', or '!'
#   - contains at least MIN_SENTENCE_WORDS words
MIN_SENTENCE_WORDS = 5

_ABBREVIATIONS = re.compile(r"\b(p|pp|e\.g|i\.e|vs|fig|eq|no|approx|etc)\b\.", flags=re.IGNORECASE)
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")
_START_OK = re.compile(r"^[\"'“”‘’]?[A-Z0-9]")
_END_OK = re.compile(r"[.!?][\"'””’]?$")


def split_sentences(text: str) -> list[str]:
    """Split text into sentences, protecting common abbreviations."""
    protected = _ABBREVIATIONS.sub(lambda m: m.group(0).replace(".", "<DOT>"), text)
    parts = _SENTENCE_SPLIT.split(protected.strip())
    return [part.strip().replace("<DOT>", ".") for part in parts if part.strip()]


def is_valid_sentence(sentence: str) -> bool:
    """Apply the sentence validity rules from the generation spec."""
    sentence = sentence.strip()
    if not sentence:
        return False
    word_count = len(sentence.split())
    if word_count < MIN_SENTENCE_WORDS:
        return False
    if not _START_OK.match(sentence):
        return False
    if not _END_OK.search(sentence):
        return False
    return True


def _normalize(sentence: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9\s]", " ", sentence.lower())).strip()


def extract_complete_sentences(chunks: list[dict[str, object]]) -> list[str]:
    """Extract valid sentences from every chunk and merge breaks at boundaries.

    A chunk that ends mid-sentence (no trailing terminator) carries its tail
    into the next chunk; if the next chunk starts with a lowercase continuation,
    the two pieces are joined into a single complete sentence.
    """
    sentences: list[str] = []
    carry = ""
    for chunk in chunks:
        text = str(chunk["text"])
        parts = split_sentences(text)
        if not parts:
            continue
        first = parts[0]
        rest = parts[1:]
        if carry and first and not first[:1].isupper():
            # The previous chunk stopped mid-sentence; stitch it back together.
            joined = (carry + " " + first).strip()
            sentences.append(joined)
        elif carry:
            sentences.append(carry)  # keep the previous tail as its own sentence
            sentences.append(first)
        else:
            sentences.append(first)
        # Trailing fragment of this chunk is held for the next chunk.
        last = rest[-1] if rest else first
        if not _END_OK.search(last):
            carry = last
            rest = rest[:-1] if rest else []
        else:
            carry = ""
        sentences.extend(rest)
    if carry:
        sentences.append(carry)
    return sentences


def deduplicate_sentences(sentences: list[str]) -> list[str]:
    """Drop repeated sentences (typically from chunk overlap) preserving order."""
    seen: set[str] = set()
    unique: list[str] = []
    for sentence in sentences:
        key = _normalize(sentence)
        if key and key not in seen:
            seen.add(key)
            unique.append(sentence)
    return unique


def _source_metadata(chunks: list[dict[str, object]]) -> list[dict[str, object]]:
    """De-duplicated, ordered source provenance for the cleaned evidence."""
    seen: set[str] = set()
    metadata: list[dict[str, object]] = []
    for chunk in chunks:
        document = str(chunk["document_name"])
        page = chunk.get("page_number")
        key = f"{document}:{page}"
        if key in seen:
            continue
        seen.add(key)
        metadata.append({"document_name": document, "page_number": page})
    return metadata


def preprocess_context(chunks: list[dict[str, object]]) -> dict[str, object]:
    """Full context cleaning pipeline.

    Returns:
        {
            "sentences": [valid complete sentences],
            "evidence": single newline-joined string for prompts,
            "metadata": [{"document_name", "page_number"}] de-duplicated,
        }
    """
    raw = extract_complete_sentences(chunks)
    cleaned = [s for s in raw if is_valid_sentence(s)]
    cleaned = deduplicate_sentences(cleaned)
    return {
        "sentences": cleaned,
        "evidence": "\n".join(cleaned),
        "metadata": _source_metadata(chunks),
    }
SUMMARIZE_SYSTEM_PROMPT = (
    "You are an evidence summarizer for a retrieval-augmented generation system. "
    "You compress retrieved evidence into one short, faithful paragraph."
)

SUMMARIZE_PROMPT = """Condense the evidence sentences below into a single readable paragraph
that supports answering this question: {question}

Rules:
- Use ONLY facts that appear in the evidence.
- Combine related facts into flowing prose; never list them.
- Preserve precise numbers and proper names exactly.
- Do not add outside knowledge or opinions.
- Keep it under 180 words.

Evidence:
{evidence}

Summary:
"""

MAX_FALLBACK_SENTENCES = 8


def summarize_evidence(question: str, sentences: list[str]) -> str:
    """Compress cleaned evidence into a faithful summary paragraph.

    Context compression must NEVER create (or infer) new facts, so we use
    extractive compression only: the original sentences are joined verbatim.
    No LLM summarization is used, because an LLM paraphrasing pass can
    introduce unsupported information.
    """
    if not sentences:
        return ""
    return " ".join(sentences[:MAX_FALLBACK_SENTENCES])