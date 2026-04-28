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
    assert "Revenue" in names or "Ebitda" in names, (
        f"Expected Revenue or Ebitda from accounting text. Got: {names}"
    )


# ── UAE Legal NER tests ───────────────────────────────────────────

def test_uae_law_number_extracted(graph):
    """Federal Decree-Law numbers are recognised as LAW entities."""
    graph.extract_and_store("doc_law1", 0,
        "Federal Decree-Law No. 28 of 2005 on Personal Status governs wills and inheritance.")
    rows = graph.get_entities_for_doc("doc_law1")
    names = [r["name"] for r in rows]
    assert any("28" in n or "Decree-Law" in n for n in names), f"Got: {names}"


def test_uae_article_ref_extracted(graph):
    """Article references are recognised as LAW entities."""
    graph.extract_and_store("doc_law2", 0,
        "Article 4 of the Wills and Probate Registry Law sets distribution rules.")
    rows = graph.get_entities_for_doc("doc_law2")
    names = [r["name"] for r in rows]
    assert any("Article" in n or "article" in n.lower() for n in names), f"Got: {names}"


def test_legal_terms_extracted(graph):
    """Core legal terms (inheritance, estate, beneficiary) are recognised."""
    graph.extract_and_store("doc_law3", 0,
        "The estate shall be distributed equally among the beneficiaries as per the will.")
    rows = graph.get_entities_for_doc("doc_law3")
    names = {r["name"].lower() for r in rows}
    legal_matches = names & {"estate", "will", "beneficiaries", "inheritance"}
    assert legal_matches, f"No legal terms extracted. Got: {names}"


def test_aed_amount_extracted(graph):
    """AED monetary amounts are recognised as MONEY entities."""
    graph.extract_and_store("doc_fin1", 0,
        "The total estate value is AED 10,000,000 to be distributed.")
    rows = graph.get_entities_for_doc("doc_fin1")
    types = [r["entity_type"] for r in rows]
    assert "MONEY" in types, f"Got types: {types}"


def test_search_by_entities_returns_chunks(graph):
    """search_by_entities finds chunks that contain matching entity names."""
    graph.store_entities("docX", chunk_index=0,
                         entities=[("Inheritance", "LEGAL"), ("Estate", "LEGAL")])
    graph.store_entities("docY", chunk_index=2,
                         entities=[("Estate", "LEGAL"), ("Beneficiary", "LEGAL")])
    results = graph.search_by_entities(["inheritance", "estate"], top_k=5)
    chunk_ids = {r["chunk_id"] for r in results}
    assert "docX_chunk_0" in chunk_ids
    assert "docY_chunk_2" in chunk_ids


def test_search_by_entities_empty_returns_empty(graph):
    """Querying with no matching entities returns empty list."""
    results = graph.search_by_entities(["nonexistent_entity_xyz_12345"], top_k=5)
    assert results == []


def test_search_by_entities_scores_higher_for_more_matches(graph):
    """Chunk with 2 matching entities scores higher than chunk with 1."""
    graph.store_entities("docZ", chunk_index=0,
                         entities=[("Wills", "LEGAL"), ("Estate", "LEGAL")])
    graph.store_entities("docZ", chunk_index=1,
                         entities=[("Wills", "LEGAL")])
    results = graph.search_by_entities(["wills", "estate"], top_k=5)
    scores = {r["chunk_id"]: r["graph_score"] for r in results}
    assert scores.get("docZ_chunk_0", 0) > scores.get("docZ_chunk_1", 0)


def test_search_by_entities_empty_list_returns_empty(graph):
    """Empty list and whitespace-only inputs return empty list."""
    assert graph.search_by_entities([]) == []
    assert graph.search_by_entities(["", "  "]) == []
