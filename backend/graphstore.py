"""Phase 4 — Local graph store built from ingested documents.

A lightweight ``networkx`` knowledge graph that models the relationships inside
the source library:

    Document -> Section/Category -> Entity -> Concept -> Related Concept

Every node created from an ingested chunk carries provenance back to the
original source (document, page, chunk, source file) so a graph fact is never
generated without a traceable origin.

Design decisions:
  * Local only — no Neo4j. The AGENTS spec explicitly prefers a clean local
    implementation first.
  * Built deterministically from chunk text using a simple entity/keyword
    extractor (proper-noun-ish terms + higher-frequency keywords) so it works
    offline with no NER model.
  * Graph retrieval is optional and purely additive: when disabled, normal
    FAISS RAG behaves exactly as before.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Iterable

import networkx as nx

# Node kinds in the graph.
NODE_DOCUMENT = "DOCUMENT"
NODE_SECTION = "SECTION"
NODE_ENTITY = "ENTITY"
NODE_CONCEPT = "CONCEPT"

STOP_WORDS = {
    "the", "and", "for", "with", "that", "this", "from", "are", "was", "were",
    "has", "have", "been", "into", "only", "must", "will", "can", "may", "shall",
    "also", "each", "their", "they", "them", "than", "then", "when", "where",
    "which", "what", "who", "how", "about", "should", "would", "could", "does",
    "other", "such", "there", "these", "those", "more", "most", "many", "all",
    "any", "per", "some", "not", "its", "his", "her", "our", "your", "their",
}

_ENTITY_RE = re.compile(r"\b[A-Z][a-z]+\b")


def _candidate_entities(text: str) -> list[str]:
    """Extract likely proper-noun entities (capitalized words)."""
    entities = []
    for token in _ENTITY_RE.findall(text):
        if token.lower() not in STOP_WORDS and len(token) > 2:
            entities.append(token)
    return entities


def _concept_terms(text: str) -> list[str]:
    """Extract informative keyword concepts (non-stopword, >= 4 letters)."""
    words = re.findall(r"[a-zA-Z]{4,}", text.lower())
    seen: set[str] = set()
    out = []
    for word in words:
        if word in STOP_WORDS or word in seen:
            continue
        seen.add(word)
        out.append(word)
    return out


def _section_of(doc: str) -> str | None:
    """Best-effort section label derived from the document stem."""
    stem = Path(doc).stem or doc
    m = re.search(r"[A-Za-z]{3,}", stem)
    return m.group(0).capitalize() if m else None


def _keyword_terms(text: str) -> list[str]:
    return _concept_terms(text)
class KnowledgeGraph:
    """A ``networkx`` graph with provenance attached to every node."""

    def __init__(self, graph: nx.Graph | None = None) -> None:
        self.graph = graph if graph is not None else nx.Graph()

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------
    def build(self, chunks: list[dict[str, object]]) -> "KnowledgeGraph":
        """Build the graph from metadata-bearing chunk dictionaries."""
        g = self.graph
        for chunk in chunks:
            text = str(chunk.get("text", "")).strip()
            doc = str(chunk.get("document_name", chunk.get("file", "unknown")))
            page = chunk.get("page_number")
            chunk_id = str(chunk.get("chunk_id", f"{doc}:p{page or 0}"))

            doc_node = ("doc", doc)
            g.add_node(doc_node, kind=NODE_DOCUMENT, provenance={"document": doc})

            section_key = ("section", doc, _section_of(text) or "general")
            g.add_edge(doc_node, section_key, kind="CONTAINS")
            section_node = section_key

            for entity in _candidate_entities(text):
                enode = ("ent", entity)
                g.add_node(enode, kind=NODE_ENTITY, provenance={"document": doc, "page": page, "chunk_id": chunk_id})
                g.add_edge(section_node, enode, kind="MENTIONS")

            for concept in _keyword_terms(text):
                cnode = ("con", concept)
                g.add_node(cnode, kind=NODE_CONCEPT, provenance={"document": doc, "page": page, "chunk_id": chunk_id})
                g.add_edge(section_node, cnode, kind="RELATES")
                for entity in _candidate_entities(text):
                    g.add_edge(("ent", entity), cnode, kind="CO_OCCURS")
        return self

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------
    def neighbor_chunk_provenance(self, nodes: Iterable) -> list[dict]:
        """Return provenance facts for entity/concept nodes supplied by caller."""
        out: list[dict] = []
        seen: set = set()
        for node in nodes:
            data = self.graph.nodes.get(node)
            if not data or node in seen:
                continue
            seen.add(node)
            prov = dict(data.get("provenance", {}))
            prov["node"] = node[1] if isinstance(node, tuple) and len(node) > 1 else str(node)
            prov["kind"] = data.get("kind")
            out.append(prov)
        return out

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------
    def save(self, path: str | Path) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(nx.node_link_data(self.graph)), encoding="utf-8")

    def load(self, path: str | Path) -> None:
        self.graph = nx.node_link_graph(json.loads(Path(path).read_text(encoding="utf-8")))

    @property
    def node_count(self) -> int:
        return self.graph.number_of_nodes()

    @property
    def edge_count(self) -> int:
        return self.graph.number_of_edges()