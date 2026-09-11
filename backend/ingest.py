"""Handbook ingestion with provenance-preserving, sentence-aware chunking."""
from __future__ import annotations

import re
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Iterable

from pypdf import PdfReader


@dataclass(frozen=True)
class Chunk:
    text: str
    document_name: str
    page_number: int | None
    chunk_id: str

    def metadata(self) -> dict[str, str | int | None]:
        return {"document_name": self.document_name, "page_number": self.page_number, "chunk_id": self.chunk_id}


# Default chunking parameters (natural-generation pipeline):
CHUNK_SIZE = 800
CHUNK_OVERLAP = 150

_ABBREVIATIONS = re.compile(r"\b(p|pp|e\.g|i\.e|vs|fig|eq|no|approx|etc)\b\.", flags=re.IGNORECASE)
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")


def clean_text(text: str) -> str:
    """Normalize whitespace without changing the handbook's meaning."""
    return " ".join(text.replace("\x00", " ").split())


def _load_pages(path: Path) -> Iterable[tuple[int | None, str]]:
    if path.suffix.lower() == ".txt":
        yield None, path.read_text(encoding="utf-8")
    elif path.suffix.lower() == ".pdf":
        for number, page in enumerate(PdfReader(str(path)).pages, start=1):
            yield number, page.extract_text() or ""
    else:
        raise ValueError(f"Unsupported document type: {path.suffix}. Use PDF or TXT.")


def _split_sentences(text: str) -> list[str]:
    """Sentence splitter used for sentence-aware chunk boundaries."""
    protected = _ABBREVIATIONS.sub(lambda m: m.group(0).replace(".", "<DOT>"), text)
    parts = _SENTENCE_SPLIT.split(protected.strip())
    return [part.strip().replace("<DOT>", ".") for part in parts if part.strip()]


def sentence_chunks(text: str, chunk_size: int = CHUNK_SIZE, chunk_overlap: int = CHUNK_OVERLAP) -> list[str]:
    """Chunk text without splitting sentences mid-way.

    Sentences are packed into chunks up to ``chunk_size`` characters. Each new
    chunk is seeded from the *complete trailing sentences* of the previous chunk
    so every chunk starts at a sentence boundary and ``chunk_overlap`` characters
    carry across. A single sentence longer than ``chunk_size`` is hard-split as a
    last resort.
    """
    sentences = _split_sentences(text)
    if not sentences:
        return [text] if text.strip() else []

    chunks: list[str] = []
    current = ""

    def emit() -> str | None:
        nonlocal current
        if not current.strip():
            current = ""
            return None
        emitted = current.strip()
        current = ""
        return emitted

    def overlap_seed(previous: str) -> str:
        """Return the previous chunk's trailing sentences covering the overlap."""
        previous_sentences = _split_sentences(previous)
        seed_parts: list[str] = []
        total = 0
        for sentence in reversed(previous_sentences):
            if seed_parts and total >= chunk_overlap:
                break
            seed_parts.insert(0, sentence)
            total += len(sentence) + 1
        return " ".join(seed_parts)

    for sentence in sentences:
        candidate = (current + " " + sentence).strip() if current else sentence
        if len(candidate) <= chunk_size:
            current = candidate
            continue

        # The next sentence does not fit; close the current chunk if it has content.
        if current:
            emitted = emit()
            if emitted:
                chunks.append(emitted)

        if len(sentence) <= chunk_size:
            current = sentence
        else:
            # Rare: one sentence alone exceeds the budget; hard-split it.
            start = 0
            while start < len(sentence):
                chunks.append(sentence[start : start + chunk_size].strip())
                start += chunk_size
            current = ""

        # Start the new chunk from sentence-boundary overlap of the previous chunk.
        if chunks:
            previous = chunks[-1]
            seed = overlap_seed(previous)
            current = (seed + " " + current).strip() if seed and current else (seed or current)

    emitted = emit()
    if emitted:
        chunks.append(emitted)
    return [c for c in chunks if c]


def ingest_file(path: str | Path, chunk_size: int = CHUNK_SIZE, chunk_overlap: int = CHUNK_OVERLAP) -> list[Chunk]:
    source = Path(path)
    if not source.exists():
        raise FileNotFoundError(source)
    chunks: list[Chunk] = []
    for page_number, raw_text in _load_pages(source):
        cleaned = clean_text(raw_text)
        for part in sentence_chunks(cleaned, chunk_size=chunk_size, chunk_overlap=chunk_overlap):
            chunk_id = f"{source.stem}-p{page_number or 1}-c{len(chunks):04d}"
            chunks.append(Chunk(part, source.name, page_number, chunk_id))
    if not chunks:
        raise ValueError(f"No extractable text found in {source}")
    return chunks


def ingest_paths(paths: Iterable[str | Path]) -> list[Chunk]:
    """Index each source separately so returned citations identify their origin."""
    chunks: list[Chunk] = []
    for path in paths:
        chunks.extend(ingest_file(path))
    if not chunks:
        raise ValueError("No PDF or TXT source files were provided.")
    return chunks


def chunks_as_dicts(chunks: list[Chunk]) -> list[dict[str, object]]:
    return [asdict(chunk) for chunk in chunks]
