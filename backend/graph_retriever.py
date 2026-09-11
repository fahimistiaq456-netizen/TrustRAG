"""Phase 4 — Graph-based retrieval and evidence fusion.

A question first undergoes light query understanding (entity + concept term
extraction), then a seed set of graph nodes is gathered from those terms. The
graph expands to neighbouring entity/concept nodes to surface *related* facts,
whose provenance is fused with the FAISS chunks before reranking / verification.

Graph retrieval is optional (``HALLUFIX_GRAPH_ENABLED``). When disabled, or when
no graph/index is available, the FAISS chunks are returned unchanged so ordinary
RAG behaves exactly as before.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Callable

from .config import get_settings
from .graphstore import (
    NODE_CONCEPT as NODE_CONCEPT_KIND,
    NODE_ENTITY as NODE_ENTITY_KIND,
    KnowledgeGraph,
    _candidate_entities,
    _keyword_terms,
)

logger = logging.getLogger(__name__)

DEFAULT_GRAPH_PATH = "data/index/graph.json"


def _load_graph(path: str | Path = DEFAULT_GRAPH_PATH) -> KnowledgeGraph | None:
    """Load the persisted graph; return None when missing or corrupt."""
    p = Path(path)
    if not p.exists():
        return None
    try:
        kg = KnowledgeGraph()
        kg.load(p)
        return kg
    except Exception as exc:  # noqa: BLE001
        logger.warning("Could not load graph store at %s: %s", p, exc)
        return None


def build_graph(chunks: list[dict[str, object]], path: str | Path = DEFAULT_GRAPH_PATH) -> KnowledgeGraph:
    """Build and persist the knowledge graph from indexed chunks (see graphstore)."""
    kg = KnowledgeGraph().build(chunks)
    kg.save(path)
    return kg


def graph_retrieve(
    question: str,
    faiss_chunks: list[dict[str, object]],
    graph_path: str | Path = DEFAULT_GRAPH_PATH,
    max_neighbors: int | None = None,
) -> tuple[list[dict[str, object]], bool]:
    """Retrieve, expand and fuse graph evidence with the FAISS chunks.

    Returns ``(fused_chunks, graph_used)``. When graph retrieval is disabled or
    the graph cannot be built/loaded, ``(faiss_chunks, False)`` is returned.
    """
    if not get_settings().graph_enabled:
        return faiss_chunks, False
    kg = _load_graph(graph_path)
    if kg is None:
        logger.warning("Graph disabled or missing at %s; RAG continues with FAISS.", graph_path)
        return faiss_chunks, False
    if not faiss_chunks:
        return faiss_chunks, False

    max_neighbors = max_neighbors or get_settings().graph_neighbors
    seeds = _find_seed_nodes(kg, question)
    expanded = _expand_seeds(kg, seeds, max_neighbors=max_neighbors)
    prov = kg.neighbor_chunk_provenance(expanded)

    # Deduplicate facts that trace back to the same chunk as FAISS evidence to
    # avoid cramming the prompt with repeats.
    fused = _fuse_chunks(faiss_chunks, prov, question)
    return fused, True


def _find_seed_nodes(kg: KnowledgeGraph, question: str) -> set:
    """Return graph nodes whose label matches query entities / concepts."""
    entities = {e.lower() for e in _candidate_entities(question)}
    concepts = set(_keyword_terms(question))
    seeds: set = set()
    g = kg.graph
    for node, data in g.nodes(data=True):
        label = node[1].lower() if isinstance(node, tuple) and len(node) > 1 else str(node).lower()
        if label in entities or label in concepts:
            seeds.add(node)
            data = g.nodes[node]
            if data and data.get("kind") in (NODE_ENTITY_KIND, NODE_CONCEPT_KIND):
                seeds.add(node)
    return seeds


def _expand_seeds(kg: KnowledgeGraph, seeds: set, max_neighbors: int) -> set:
    """Breadth-first expansion of seed nodes through graph edges."""
    expanded = set(seeds)
    for seed in seeds:
        neighbors = list(kg.graph.neighbors(seed))[:max_neighbors]
        for neighbor in neighbors:
            expanded.add(neighbor)
    return expanded


def _fuse_chunks(faiss_chunks: list[dict[str, object]], provenance: list[dict], question: str) -> list[dict[str, object]]:
    """Merge graph provenance into FAISS chunks, de-duping on chunk provenance.

    Graph facts are attached to an existing FAISS chunk where possible, or
    appended as lightweight pseudo-chunks with a ``from_graph`` flag.
    """
    by_key: dict = {}
    for chunk in faiss_chunks:
        key = str(chunk.get("chunk_id", chunk.get("document_name")))
        by_key.setdefault(key, chunk)

    for fact in provenance:
        key = _provenance_key(fact)
        if key in by_key:
            by_key[key].setdefault("graph_nodes", []).append(fact["node"])
            continue
        pseudo = {
            "text": _fact_text(fact),
            "document_name": fact.get("document", "graph"),
            "page_number": fact.get("page"),
            "chunk_id": fact.get("chunk_id", key),
            "similarity_score": 0.0,
            "from_graph": True,
            "graph_nodes": [fact["node"]],
        }
        by_key.setdefault(key, pseudo)

    # Keep FAISS order first, then graph-only facts.
    ordered = list(faiss_chunks)
    appended = [c for c in by_key.values() if c.get("from_graph") and c not in ordered]
    return ordered + appended


def _provenance_key(fact: dict) -> str:
    return str(fact.get("chunk_id") or f"{fact.get('document')}:p{fact.get('page')}")


def _fact_text(fact: dict) -> str:
    return f"Graph relation involving {fact.get('node')} (kind {fact.get('kind')}) from {fact.get('document')}."