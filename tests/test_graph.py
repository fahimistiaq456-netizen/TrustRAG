"""Tests for Phase 4 — graph construction, provenance and retrieval."""
from __future__ import annotations

import pytest

from backend.config import get_settings
from backend.graph_retriever import (
    _find_seed_nodes,
    build_graph,
    graph_retrieve,
)
from backend.graphstore import KnowledgeGraph, NODE_CONCEPT, NODE_ENTITY


def _chunk(text: str, doc: str = "handbook.md", page: int = 1, cid: str = "c1") -> dict:
    return {"text": text, "document_name": doc, "page_number": page, "chunk_id": cid, "similarity_score": 0.6}


def test_build_creates_nodes_with_provenance(tmp_path):
    kg = KnowledgeGraph().build([
        _chunk("The Admission Office requires a minimum GPA of 2.0 for eligibility.", doc="policy.md", cid="c1"),
    ])
    assert kg.node_count > 3  # doc + section + entities + concepts
    facts = kg.neighbor_chunk_provenance(kg.graph.nodes)
    assert all("document" in f for f in facts)


def test_build_and_load_roundtrip(tmp_path):
    kg = KnowledgeGraph().build([_chunk("Admission requires GPA eligibility.", doc="policy.md", cid="c1")])
    path = tmp_path / "graph.json"
    kg.save(path)
    kg2 = KnowledgeGraph()
    kg2.load(path)
    assert kg2.node_count == kg.node_count


def test_seed_nodes_found_from_query_terms():
    kg = KnowledgeGraph().build([
        _chunk("The University requires a minimum GPA of 2.0 for admission eligibility.", doc="policy.md", cid="c1"),
    ])
    seeds = _find_seed_nodes(kg, "What is the GPA admission requirement?")
    assert seeds  # at least GPA or Admission should be a seed


def test_graph_retrieve_disabled_returns_faiss_chunks(tmp_path):
    from backend.config import get_settings
    get_settings().graph_enabled = False
    cands = [_chunk("a", cid="c1")]
    fused, used = graph_retrieve("question", cands, graph_path=str(tmp_path / "missing.json"))
    assert fused == cands
    assert used is False


def test_graph_retrieve_no_graph_file_degrades(tmp_path):
    from backend.config import get_settings
    get_settings().graph_enabled = True
    cands = [_chunk("a", cid="c1")]
    fused, used = graph_retrieve("question", cands, graph_path=str(tmp_path / "missing.json"))
    assert fused == cands
    assert used is False
    get_settings().graph_enabled = False


def test_graph_retrieve_fuses_evidence(tmp_path):
    from backend.config import get_settings
    get_settings().graph_enabled = True
    kg_path = tmp_path / "g.json"
    build_graph([_chunk("The University Admission Office requires a minimum GPA of 2.0.", doc="policy.md", cid="c1")], path=str(kg_path))
    cands = [_chunk("University policies apply.", doc="policy.md", cid="c1")]
    fused, used = graph_retrieve("What minimum GPA for admission?", cands, graph_path=str(kg_path))
    assert used is True
    assert len(fused) >= len(cands)
    get_settings().graph_enabled = False