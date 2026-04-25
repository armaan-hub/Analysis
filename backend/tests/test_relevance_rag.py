"""Tests for relevance-first RAG: score threshold + default category filter."""
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from core.rag_engine import RAGEngine
from config import settings


def test_rag_min_score_default():
    """rag_min_score must exist and default to 0.45."""
    assert hasattr(settings, "rag_min_score")
    assert 0.0 < settings.rag_min_score < 1.0
    assert settings.rag_min_score == pytest.approx(0.45)


def _make_engine_with_results(raw_results: list[dict]) -> RAGEngine:
    """Build a RAGEngine whose ChromaDB collection returns raw_results."""
    engine = object.__new__(RAGEngine)
    engine.embedding_provider = MagicMock()
    engine.embedding_provider.embed_query = AsyncMock(return_value=[0.1] * 1024)

    mock_collection = MagicMock()
    mock_collection.count.return_value = 10
    # Convert score back to distance for ChromaDB format: distance = 1 - score
    mock_collection.query.return_value = {
        "documents": [[r["text"] for r in raw_results]],
        "metadatas": [[r["metadata"] for r in raw_results]],
        "distances": [[1 - r["score"] for r in raw_results]],
        "ids": [[f"chunk_{i}" for i in range(len(raw_results))]],
    }
    engine.collection = mock_collection
    return engine


@pytest.mark.asyncio
async def test_search_filters_below_threshold():
    """Chunks with score < min_score must NOT appear in search results."""
    raw = [
        {"text": "VAT on hotel apartments is 5%.", "metadata": {"doc_id": "d1", "category": "finance"}, "score": 0.82},
        {"text": "Trail Balance debit total.", "metadata": {"doc_id": "d2", "category": "general"}, "score": 0.21},
    ]
    engine = _make_engine_with_results(raw)
    results = await engine.search("VAT hotel apartment", top_k=5, min_score=0.45)
    assert len(results) == 1
    assert results[0]["text"] == "VAT on hotel apartments is 5%."
    assert results[0]["score"] == pytest.approx(0.82)


@pytest.mark.asyncio
async def test_search_returns_empty_when_all_below_threshold():
    """If all chunks score below threshold, return empty list — never contaminate."""
    raw = [
        {"text": "Debit 1000 Credit 1000.", "metadata": {"doc_id": "d1", "category": "general"}, "score": 0.18},
        {"text": "Opening balance 50000.", "metadata": {"doc_id": "d1", "category": "general"}, "score": 0.22},
    ]
    engine = _make_engine_with_results(raw)
    results = await engine.search("VAT hotel apartment legal compliance", top_k=5, min_score=0.45)
    assert results == []


@pytest.mark.asyncio
async def test_search_respects_max_results_after_threshold():
    """After threshold filtering, cap at top 8 results by score."""
    raw = [
        {"text": f"Relevant chunk {i}", "metadata": {"doc_id": f"d{i}", "category": "law"}, "score": 0.90 - i * 0.02}
        for i in range(12)  # 12 chunks all above threshold
    ]
    engine = _make_engine_with_results(raw)
    results = await engine.search("law query", top_k=12, min_score=0.45)
    assert len(results) <= 8
    # Must be sorted by score descending
    scores = [r["score"] for r in results]
    assert scores == sorted(scores, reverse=True)


def test_bulk_ingest_passes_category_to_ingest_chunks():
    """bulk_ingest.py must pass category= and original_name= to ingest_chunks().

    Without this, all pre-loaded UAE law/finance documents get category='general'
    in ChromaDB and become completely invisible to category-filtered searches.
    """
    source = (Path(__file__).parent.parent / "bulk_ingest.py").read_text(encoding="utf-8")
    assert "category=category" in source, (
        "bulk_ingest.py must pass category=category to ingest_chunks(). "
        "Without this, all pre-loaded documents get category='general' and become unsearchable."
    )
    assert "original_name=name" in source or "original_name=file_path.name" in source, (
        "bulk_ingest.py must pass original_name= to ingest_chunks() for readable source names."
    )


def test_bulk_retag_script_exists_and_has_correct_structure():
    """bulk_retag.py must exist and define a main() coroutine."""
    retag_path = Path(__file__).parent.parent / "bulk_retag.py"
    assert retag_path.exists(), "backend/bulk_retag.py must exist"
    source = retag_path.read_text(encoding="utf-8")
    assert "async def main" in source, "bulk_retag.py must define async def main()"
    assert "collection.update" in source, (
        "bulk_retag.py must call collection.update() to retag existing chunks"
    )
    assert "metadata_json" in source, (
        "bulk_retag.py must read category from Document.metadata_json"
    )


@pytest.mark.asyncio
async def test_chat_default_filter_is_law_finance(client):
    """Without selected_doc_ids, RAG must use category IN ['law','finance'] — not unfiltered."""
    search_calls = []

    async def _fake_search(query, top_k=5, filter=None, min_score=None, **kw):
        search_calls.append({"filter": filter, "min_score": min_score})
        return []

    with (
        patch("api.chat.rag_engine.search", side_effect=_fake_search),
    ):
        resp = await client.post(
            "/api/chat/send",
            json={"message": "What is UAE VAT on hotel apartments?", "use_rag": True, "stream": False},
        )

    assert resp.status_code == 200
    assert search_calls, "rag_engine.search must have been called"
    call = search_calls[0]
    assert call["filter"] == {"category": {"$in": ["law", "finance"]}}, (
        f"Expected law+finance default filter, got: {call['filter']}"
    )
    assert call["min_score"] == pytest.approx(0.45), (
        f"Expected min_score=0.45, got: {call['min_score']}"
    )


@pytest.mark.asyncio
async def test_chat_selected_docs_override_default_filter(client):
    """With selected_doc_ids, RAG must use doc_id filter, not the default category filter."""
    search_calls = []

    async def _fake_search(query, top_k=5, filter=None, min_score=None, **kw):
        search_calls.append({"filter": filter})
        return []

    with (
        patch("api.chat.rag_engine.search", side_effect=_fake_search),
    ):
        resp = await client.post(
            "/api/chat/send",
            json={
                "message": "Summarise my trail balance",
                "use_rag": True,
                "stream": False,
                "selected_doc_ids": ["doc-tb-001"],
            },
        )

    assert resp.status_code == 200
    assert search_calls
    assert search_calls[0]["filter"] == {"doc_id": {"$in": ["doc-tb-001"]}}, (
        f"Expected doc_id filter, got: {search_calls[0]['filter']}"
    )


@pytest.mark.asyncio
async def test_chat_empty_search_results_means_no_sources(client):
    """When all RAG results are below threshold (empty list), response must have empty sources."""
    with (
        patch("api.chat.rag_engine.search", new=AsyncMock(return_value=[])),
    ):
        resp = await client.post(
            "/api/chat/send",
            json={"message": "Random question", "use_rag": True, "stream": False},
        )

    assert resp.status_code == 200
    sources = resp.json()["message"].get("sources")
    # Accept either None or [] for empty sources (both indicate no sources available)
    assert sources in (None, []), f"Expected empty sources (None or []), got: {sources}"
