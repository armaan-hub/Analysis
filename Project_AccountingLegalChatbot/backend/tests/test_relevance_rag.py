"""Tests for relevance-first RAG: score threshold + default category filter."""
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from core.rag_engine import RAGEngine
from core.chat.domain_classifier import ClassifierResult, DomainLabel
from config import settings


def test_rag_min_score_default():
    """rag_min_score must exist and default to 0.30."""
    assert hasattr(settings, "rag_min_score")
    assert 0.0 < settings.rag_min_score < 1.0
    assert settings.rag_min_score == pytest.approx(0.30)


def _make_engine_with_results(raw_results: list[dict]) -> RAGEngine:
    """Build a RAGEngine whose ChromaDB collection returns raw_results."""
    engine = object.__new__(RAGEngine)
    engine.embedding_provider = MagicMock()
    engine.embedding_provider.embed_query = AsyncMock(return_value=[0.1] * 1024)

    mock_collection = MagicMock()
    mock_collection.count.return_value = 10
    # Convert score back to ChromaDB cosine distance: score = 1 - dist/2  →  dist = 2*(1-score)
    mock_collection.query.return_value = {
        "documents": [[r["text"] for r in raw_results]],
        "metadatas": [[r["metadata"] for r in raw_results]],
        "distances": [[2 * (1 - r["score"]) for r in raw_results]],
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
    """After threshold filtering, cap at top_k results by score."""
    raw = [
        {"text": f"Relevant chunk {i}", "metadata": {"doc_id": f"d{i}", "category": "law"}, "score": 0.90 - i * 0.02}
        for i in range(12)  # 12 chunks all above threshold
    ]
    engine = _make_engine_with_results(raw)
    # top_k=8: even with 12 chunks available, must return at most 8
    results = await engine.search("law query", top_k=8, min_score=0.45)
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
    # The filter must always include the law+finance category guard (not unfiltered).
    # Domain filtering may also be applied on top (via _build_rag_domain_filter).
    cat_filter = {"category": {"$in": ["law", "finance"]}}
    actual = call["filter"]
    has_category = actual == cat_filter or (
        "$and" in actual and any(c == cat_filter for c in actual["$and"])
    )
    assert has_category, (
        f"Expected law+finance category filter to be present, got: {actual}"
    )
    assert actual is not None, "Filter must not be None (search must not be unfiltered)"
    assert call["min_score"] == pytest.approx(0.30), (
        f"Expected min_score=0.30, got: {call['min_score']}"
    )


@pytest.mark.asyncio
async def test_chat_selected_docs_override_default_filter(client):
    """Analyst mode with selected_doc_ids uses doc_id filter only (client workbooks are valid)."""
    search_calls = []

    async def _fake_search(query, top_k=5, filter=None, min_score=None, **kw):
        search_calls.append({"filter": filter, "min_score": min_score})
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
                "mode": "analyst",
                "selected_doc_ids": ["doc-tb-001"],
            },
        )

    assert resp.status_code == 200
    assert search_calls
    call = search_calls[0]
    assert call["filter"] == {"doc_id": {"$in": ["doc-tb-001"]}}, (
        f"Expected doc_id-only filter for analyst mode, got: {call['filter']}"
    )
    assert call["min_score"] == pytest.approx(0.30), (
        f"Expected min_score=0.30 for doc-scoped search, got: {call['min_score']}"
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


_AND_FILTER = {
    "$and": [
        {"doc_id": {"$in": ["doc-tb-001"]}},
        {"category": {"$in": ["law", "finance"]}},
        {"domain": {"$in": ["corporate_tax"]}},
    ]
}


@pytest.mark.asyncio
async def test_chat_filter_analyst_mode_uses_doc_id_only(client):
    """mode=analyst + selected_doc_ids → filter is doc_id only (client workbooks allowed)."""
    search_calls = []

    async def _fake_search(query, top_k=5, filter=None, min_score=None, **kw):
        search_calls.append({"filter": filter})
        return []

    with patch("api.chat.rag_engine.search", side_effect=_fake_search):
        resp = await client.post(
            "/api/chat/send",
            json={
                "message": "Analyse my trail balance",
                "use_rag": True,
                "stream": False,
                "mode": "analyst",
                "selected_doc_ids": ["doc-tb-001"],
            },
        )

    assert resp.status_code == 200
    assert search_calls
    assert search_calls[0]["filter"] == {"doc_id": {"$in": ["doc-tb-001"]}}, (
        f"Analyst mode must use doc_id-only filter, got: {search_calls[0]['filter']}"
    )


@pytest.mark.asyncio
async def test_chat_filter_fast_mode_selected_docs_combines_and(client):
    """mode=fast + selected_doc_ids → $and filter combining doc_id with law+finance category."""
    search_calls = []

    async def _fake_search(query, top_k=5, filter=None, min_score=None, **kw):
        search_calls.append({"filter": filter})
        return []

    with patch("api.chat.rag_engine.search", side_effect=_fake_search):
        resp = await client.post(
            "/api/chat/send",
            json={
                "message": "What is VAT on hotel apartments?",
                "use_rag": True,
                "stream": False,
                "mode": "fast",
                "selected_doc_ids": ["doc-tb-001"],
            },
        )

    assert resp.status_code == 200
    assert search_calls
    # Filter must be an $and containing both doc_id scope AND law+finance category guard.
    # Domain filtering may also be included on top by _build_rag_domain_filter.
    actual = search_calls[0]["filter"]
    assert "$and" in actual, (
        f"Fast mode must use $and filter to prevent workbook contamination, got: {actual}"
    )
    clauses = actual["$and"]
    assert {"doc_id": {"$in": ["doc-tb-001"]}} in clauses, (
        f"doc_id scope clause missing. Clauses: {clauses}"
    )
    assert {"category": {"$in": ["law", "finance"]}} in clauses, (
        f"law+finance category clause missing. Clauses: {clauses}"
    )


@pytest.mark.asyncio
async def test_chat_filter_deep_mode_selected_docs_combines_and(client):
    """mode=deep_research + selected_doc_ids → $and filter combining doc_id with law+finance category."""
    search_calls = []

    async def _fake_search(query, top_k=5, filter=None, min_score=None, **kw):
        search_calls.append({"filter": filter})
        return []

    with patch("api.chat.rag_engine.search", side_effect=_fake_search):
        resp = await client.post(
            "/api/chat/send",
            json={
                "message": "Explain corporate tax compliance",
                "use_rag": True,
                "stream": False,
                "mode": "deep_research",
                "selected_doc_ids": ["doc-tb-001"],
            },
        )

    assert resp.status_code == 200
    assert search_calls
    assert search_calls[0]["filter"] == _AND_FILTER, (
        f"Deep mode must use $and filter to prevent workbook contamination, got: {search_calls[0]['filter']}"
    )


@pytest.mark.asyncio
async def test_chat_filter_analyst_no_docs_uses_law_finance(client):
    """Analyst mode with NO selected_doc_ids falls back to law+finance default filter."""
    search_calls = []

    async def _fake_search(query, top_k=5, filter=None, min_score=None, **kw):
        search_calls.append({"filter": filter})
        return []

    with patch("api.chat.rag_engine.search", side_effect=_fake_search):
        resp = await client.post(
            "/api/chat/send",
            json={
                "message": "What are the UAE VAT rules?",
                "use_rag": True,
                "stream": False,
                "mode": "analyst",
            },
        )

    assert resp.status_code == 200
    assert search_calls
    assert search_calls[0]["filter"] == {
        "$and": [
            {"category": {"$in": ["law", "finance"]}},
            {"domain": {"$in": ["vat"]}},
        ]
    }, (
        f"Analyst mode without selected_doc_ids must use law+finance+domain filter, got: {search_calls[0]['filter']}"
    )


@pytest.mark.asyncio
async def test_broad_fallback_triggered_when_domain_filter_returns_low_scores(client):
    """When domain-filtered results all score < 0.65, a broad retry should be attempted
    and its results used if they score better."""
    from unittest.mock import patch

    # Domain-filtered results: all low-score (< 0.65)
    low_score_results = [
        {"text": "Electronic devices criteria", "metadata": {"source": "VATP035.pdf", "domain": "vat", "page": 1, "doc_id": "d1", "category": "finance"}, "distance": 0.38, "score": 0.62},  # score = 1 - 0.38 = 0.62
        {"text": "VAT real estate treatment", "metadata": {"source": "RealEstate.pdf", "domain": "vat", "page": 2, "doc_id": "d2", "category": "finance"}, "distance": 0.40, "score": 0.60},  # score = 0.60
    ]

    # Broad search results: high-score (>= 0.65)
    high_score_results = [
        {"text": "UAE Civil Transactions Law Article 265 on wills", "metadata": {"source": "CivilTransactionsLaw.pdf", "domain": "general", "page": 1, "doc_id": "d3", "category": "law"}, "distance": 0.20, "score": 0.80},  # score = 0.80
        {"text": "DIFC Wills Service Centre regulations", "metadata": {"source": "DIFCWills.pdf", "domain": "general", "page": 1, "doc_id": "d4", "category": "law"}, "distance": 0.25, "score": 0.75},  # score = 0.75
    ]

    call_count = {"n": 0}

    async def mock_search(query, top_k=5, filter=None, min_score=0.3):
        call_count["n"] += 1
        # First call: domain filter applied → low scores
        # Detect domain filter by checking for domain key in filter
        has_domain = False
        if filter:
            if "$and" in filter:
                has_domain = any("domain" in clause for clause in filter["$and"])
            else:
                has_domain = "domain" in filter
        
        if has_domain:
            return low_score_results
        return high_score_results  # second call: no domain filter (broad) → high scores

    # Build a minimal non-streaming request for a wills query
    payload = {
        "conversation_id": None,
        "message": "Draft Wills for 10 Million Estate and Properties",
        "mode": "fast",
        "stream": False,
        "use_rag": True,
    }

    with patch("api.chat.rag_engine.search", side_effect=mock_search):
        with patch("api.chat.classify_domain") as mock_classify:
            mock_classify.return_value = ClassifierResult(
                domain=DomainLabel("vat"),
                confidence=0.92,
                alternatives=[],
            )
            response = await client.post("/api/chat/send", json=payload)

    # The broad fallback should have been called (2 RAG calls total)
    # and the response should contain the high-score source
    assert response.status_code == 200
    body = response.json()
    sources = body.get("message", {}).get("sources", [])
    source_names = [s.get("source", "") for s in sources]
    # At minimum, the broad search was invoked
    assert call_count["n"] >= 2, f"Expected at least 2 RAG calls (filtered + broad), got {call_count['n']}"
    # The sources should include the better broad results
    assert any("CivilTransactionsLaw" in s or "DIFCWills" in s for s in source_names), (
        f"Expected broad search results in sources, got: {source_names}"
    )
