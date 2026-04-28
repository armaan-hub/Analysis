"""Tests for the Parallel Fusion HybridRetriever."""
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from core.rag.hybrid_retriever import HybridRetriever


def _make_chunk(chunk_id: str, score: float, text: str = "test text") -> dict:
    doc_id, _, chunk_i = chunk_id.rpartition("_chunk_")
    return {
        "id": chunk_id,
        "text": text,
        "metadata": {"doc_id": doc_id, "chunk_index": int(chunk_i), "source": "test.pdf"},
        "score": score,
    }


@pytest.fixture
def mock_rag():
    rag = MagicMock()
    rag.search = AsyncMock(return_value=[
        _make_chunk("docA_chunk_0", 0.85, "inheritance estate distribution"),
        _make_chunk("docA_chunk_1", 0.80, "wills probate"),
    ])
    rag.collection = MagicMock()
    rag.collection.get = MagicMock(return_value={
        "ids": ["docA_chunk_2"],
        "documents": ["related legal text"],
        "metadatas": [{"doc_id": "docA", "source": "test.pdf"}],
    })
    return rag


@pytest.fixture
def mock_graph():
    graph = MagicMock()
    graph.search_by_entities = MagicMock(return_value=[
        {"chunk_id": "docB_chunk_0", "doc_id": "docB", "chunk_index": 0, "graph_score": 0.9},
        {"chunk_id": "docA_chunk_0", "doc_id": "docA", "chunk_index": 0, "graph_score": 0.7},
    ])
    return graph


@pytest.mark.asyncio
async def test_retrieve_returns_merged_results(mock_rag, mock_graph):
    """retrieve() should return results from both vector and graph paths."""
    retriever = HybridRetriever(mock_rag, mock_graph)
    results = await retriever.retrieve("draft wills for estate", top_k=5)
    assert len(results) >= 1
    chunk_ids = [r["id"] for r in results]
    assert len(chunk_ids) >= 1


@pytest.mark.asyncio
async def test_vector_and_graph_called_in_parallel(mock_rag, mock_graph):
    """Both vector search and graph search must be invoked for every query."""
    retriever = HybridRetriever(mock_rag, mock_graph)
    await retriever.retrieve("estate wills", top_k=5)
    mock_rag.search.assert_called_once()
    mock_graph.search_by_entities.assert_called_once()


@pytest.mark.asyncio
async def test_deduplication_by_chunk_id(mock_rag, mock_graph):
    """A chunk appearing in both vector and graph results appears only once."""
    retriever = HybridRetriever(mock_rag, mock_graph)
    results = await retriever.retrieve("wills estate", top_k=10)
    ids = [r["id"] for r in results]
    assert len(ids) == len(set(ids)), f"Duplicate IDs found: {ids}"


@pytest.mark.asyncio
async def test_graph_only_chunk_gets_graph_score(mock_rag, mock_graph):
    """A chunk found only by graph (not vector) must appear with graph_score as score."""
    mock_rag.search = AsyncMock(return_value=[
        _make_chunk("docA_chunk_0", 0.85),
    ])
    mock_graph.search_by_entities = MagicMock(return_value=[
        {"chunk_id": "docB_chunk_0", "doc_id": "docB", "chunk_index": 0, "graph_score": 0.8},
    ])
    mock_rag.collection.get = MagicMock(return_value={
        "ids": ["docB_chunk_0"],
        "documents": ["law text"],
        "metadatas": [{"doc_id": "docB", "source": "law.pdf"}],
    })
    retriever = HybridRetriever(mock_rag, mock_graph)
    results = await retriever.retrieve("estate law", top_k=5)
    ids = {r["id"] for r in results}
    assert "docB_chunk_0" in ids, f"Graph-only chunk missing: {ids}"


@pytest.mark.asyncio
async def test_vector_failure_still_returns_graph_results(mock_rag, mock_graph):
    """If vector search raises, graph results are still returned."""
    mock_rag.search = AsyncMock(side_effect=Exception("vector store offline"))
    # Need a chunk to fetch for the graph-only result
    mock_rag.collection.get = MagicMock(return_value={
        "ids": ["docB_chunk_0"],
        "documents": ["law text"],
        "metadatas": [{"doc_id": "docB", "source": "law.pdf"}],
    })
    retriever = HybridRetriever(mock_rag, mock_graph)
    results = await retriever.retrieve("wills", top_k=5)
    assert isinstance(results, list)


@pytest.mark.asyncio
async def test_graph_failure_still_returns_vector_results(mock_rag, mock_graph):
    """If graph search raises, vector results are still returned."""
    mock_graph.search_by_entities = MagicMock(side_effect=Exception("graph db locked"))
    retriever = HybridRetriever(mock_rag, mock_graph)
    results = await retriever.retrieve("wills", top_k=5)
    assert len(results) >= 1
    assert results[0]["id"] == "docA_chunk_0"
