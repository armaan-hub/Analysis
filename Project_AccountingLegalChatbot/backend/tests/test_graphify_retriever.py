"""Tests for GraphifyRetriever and /api/documents/concept-graph endpoint."""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest
from httpx import AsyncClient, ASGITransport


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_graph_data(num_nodes: int = 5) -> dict:
    """Build a minimal node-link graph dict with num_nodes nodes."""
    nodes = [
        {
            "id": f"n{i}",
            "label": f"concept_{i}" if i > 0 else "vat_registration",
            "source_file": f"file_{i}.pdf",
            "file_type": "pdf",
            "confidence": "EXTRACTED",
        }
        for i in range(num_nodes)
    ]
    links = [
        {
            "source": "n0",
            "target": "n1",
            "relation": "related_to",
            "confidence": "high",
            "confidence_score": 0.9,
        },
        {
            "source": "n1",
            "target": "n2",
            "relation": "part_of",
            "confidence": "high",
            "confidence_score": 0.8,
        },
    ]
    return {"nodes": nodes, "links": links, "directed": False, "multigraph": False, "graph": {}}


# ── Unit tests ────────────────────────────────────────────────────────────────


def test_retriever_graceful_when_graph_missing(tmp_path):
    """Retriever must not raise when graph file is absent."""
    from core.rag.graphify_retriever import GraphifyRetriever

    missing = tmp_path / "no_such_file.json"
    retriever = GraphifyRetriever(missing)

    assert retriever.is_available() is False
    assert retriever.search("vat") == []
    assert retriever.get_related_source_files("vat") == []
    assert retriever.get_concept_path("a", "b") == []


def test_retriever_loads_real_graph(tmp_path):
    """Retriever must report is_available=True when a valid graph exists."""
    from core.rag.graphify_retriever import GraphifyRetriever

    graph_file = tmp_path / "graphify_graph.json"
    graph_file.write_text(json.dumps(_make_graph_data()), encoding="utf-8")

    retriever = GraphifyRetriever(graph_file)
    assert retriever.is_available() is True


def test_search_returns_results(tmp_path):
    """Search must return GraphResult objects when a keyword matches a node label."""
    from core.rag.graphify_retriever import GraphifyRetriever, GraphResult

    graph_file = tmp_path / "graphify_graph.json"
    graph_file.write_text(json.dumps(_make_graph_data()), encoding="utf-8")

    retriever = GraphifyRetriever(graph_file)
    results = retriever.search("vat", top_k=10)

    assert len(results) > 0
    assert all(isinstance(r, GraphResult) for r in results)
    # The node labelled "vat_registration" should appear
    labels = [r.label for r in results]
    assert any("vat" in lbl.lower() for lbl in labels)


def test_get_related_source_files(tmp_path):
    """get_related_source_files must return non-empty list of strings."""
    from core.rag.graphify_retriever import GraphifyRetriever

    graph_file = tmp_path / "graphify_graph.json"
    graph_file.write_text(json.dumps(_make_graph_data()), encoding="utf-8")

    retriever = GraphifyRetriever(graph_file)
    files = retriever.get_related_source_files("vat", top_k=10)

    assert isinstance(files, list)
    assert all(isinstance(f, str) for f in files)
    assert len(files) > 0


def test_concept_path_no_path(tmp_path):
    """get_concept_path must return [] when nodes are disconnected."""
    from core.rag.graphify_retriever import GraphifyRetriever

    # Build a graph with two disconnected components
    data = {
        "nodes": [
            {"id": "a", "label": "Alpha", "source_file": "a.pdf", "file_type": "pdf"},
            {"id": "b", "label": "Beta", "source_file": "b.pdf", "file_type": "pdf"},
        ],
        "links": [],
        "directed": False,
        "multigraph": False,
        "graph": {},
    }
    graph_file = tmp_path / "g.json"
    graph_file.write_text(json.dumps(data), encoding="utf-8")

    retriever = GraphifyRetriever(graph_file)
    path = retriever.get_concept_path("Alpha", "Beta")
    assert path == []


# ── API tests ─────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_api_endpoint_returns_not_available(tmp_path):
    """GET /api/documents/concept-graph returns available=False when graph missing."""
    missing = tmp_path / "missing.json"

    # Patch the module-level singleton so the app uses a non-existent graph
    import core.rag.graphify_retriever as gr_module
    from core.rag.graphify_retriever import GraphifyRetriever

    original = gr_module.graphify_retriever
    gr_module.graphify_retriever = GraphifyRetriever(missing)

    # Also patch the api/graph.py reference
    import api.graph as graph_api_module
    graph_api_module.graphify_retriever = gr_module.graphify_retriever

    try:
        from main import app
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/api/documents/concept-graph", params={"query": "vat"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["available"] is False
        assert body["results"] == []
    finally:
        gr_module.graphify_retriever = original
        graph_api_module.graphify_retriever = original
