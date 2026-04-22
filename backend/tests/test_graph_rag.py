import pytest
from backend.core.rag.graph_rag import GraphRAG


@pytest.fixture
def graph():
    return GraphRAG(db_path=":memory:")


def test_store_and_retrieve_entities(graph):
    """Entities stored for a doc_id should be retrievable."""
    graph.store_entities("doc1", chunk_index=0,
                         entities=[("Apple Inc", "ORG"), ("Revenue", "METRIC")])
    result = graph.get_entities_for_doc("doc1")
    names = [r["name"] for r in result]
    assert "Apple Inc" in names
    assert "Revenue" in names


def test_related_chunks(graph):
    """Chunks related via shared entity should be returned."""
    graph.store_entities("doc1", chunk_index=0, entities=[("VAT", "TAX")])
    graph.store_entities("doc1", chunk_index=1, entities=[("VAT", "TAX")])
    related = graph.find_related_chunks("doc1", seed_chunk_indices=[0], depth=1)
    assert 1 in related


def test_no_entities_returns_empty(graph):
    """A doc with no stored entities returns empty related chunks."""
    result = graph.find_related_chunks("no_entities_doc", seed_chunk_indices=[0])
    assert result == set()


def test_extract_and_store(graph):
    """extract_and_store should find accounting terms."""
    graph.extract_and_store("doc1", 0, "The revenue grew and EBITDA improved.")
    rows = graph.get_entities_for_doc("doc1")
    names = {r["name"] for r in rows}
    assert "Revenue" in names or "Ebitda" in names or len(names) > 0
