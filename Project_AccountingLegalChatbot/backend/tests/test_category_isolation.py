"""
Test that category filters do NOT fall back to unfiltered RAG when they return 0 results.

This is a targeted regression test for the bug where Legal Studio (domain=law) would return
financial documents (Trail Balance.xlsx, TL-2024-25.pdf) because:
1. The category filter {"category": "law"} matched zero documents (category metadata wasn't stored during ingestion)
2. The code fell back to an unfiltered search, returning ALL documents
3. Financial docs leaked into Legal Studio results

After the fix, when a category filter yields 0 results, RAG returns empty (no fallback).
The system then falls through to web search or LLM knowledge, which is correct.
"""
import pytest
from unittest.mock import AsyncMock, patch, call
from core.chat.domain_classifier import DomainLabel, ClassifierResult
from core.llm_manager import LLMResponse


def _stub_classify_law():
    """Legal domain classification."""
    return ClassifierResult(domain=DomainLabel.GENERAL_LAW, confidence=0.95, alternatives=[])


def _stub_classify_finance():
    """Finance domain classification."""
    return ClassifierResult(domain=DomainLabel.VAT, confidence=0.92, alternatives=[])


def _mock_llm():
    """Mock LLM provider for testing."""
    m = AsyncMock()
    m.chat = AsyncMock(
        return_value=LLMResponse(
            content="Test response", tokens_used=10, provider="mock", model="mock-v1"
        )
    )

    async def _stream(*a, **kw):
        yield "data: " + '{"type":"content","text":"Test"}' + "\n\n"
        yield "data: [DONE]\n\n"

    m.chat_stream = _stream
    return m


def _stub_intent():
    """Stub intent classification."""
    return type("Intent", (), {"output_type": "answer", "topic": "legal"})()


@pytest.mark.asyncio
async def test_category_filter_no_fallback_fast_mode(client):
    """
    When a category filter (e.g., domain=law → {"category": "law"}) returns 0 results,
    the code must NOT fall back to an unfiltered search. Fast mode, streaming.
    
    Before fix: filtered search returns [] → fallback to unfiltered search → returns all docs
    After fix: filtered search returns [] → no fallback → RAG context is empty → LLM responds without RAG
    """
    # Mock rag_engine.search to return empty when called WITH a filter,
    # and non-empty if called WITHOUT a filter (to detect fallback)
    def mock_search_side_effect(*args, **kwargs):
        filter_arg = kwargs.get("filter")
        if filter_arg:
            # Filtered search returns empty (simulates no category metadata match)
            return []
        else:
            # Unfiltered search would return results (this should NOT happen after the fix)
            return [
                {"text": "Financial doc leaked", "score": 0.9, "metadata": {"source": "TL-2024-25.pdf"}}
            ]

    mock_search = AsyncMock(side_effect=mock_search_side_effect)

    with (
        patch("api.chat.classify_domain", new=AsyncMock(return_value=_stub_classify_law())),
        patch("api.chat.get_llm_provider", return_value=_mock_llm()),
        patch("api.chat.rag_engine.search", new=mock_search),
        patch("api.chat.classify_intent", new=AsyncMock(return_value=_stub_intent())),
        patch("api.chat._generate_title", new=AsyncMock()),
    ):
        resp = await client.post(
            "/api/chat/send",
            json={
                "message": "What are the legal requirements for company formation in UAE?",
                "stream": True,
                "mode": "fast",
                "domain": "law",  # Explicit Legal Studio domain
            },
        )

    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
    
    # Verify that search was called WITH a filter (the category filter)
    filtered_calls = [
        c for c in mock_search.call_args_list
        if c.kwargs.get("filter") is not None
    ]
    assert len(filtered_calls) > 0, "Expected at least one filtered search call"
    
    # CRITICAL: Verify that search was NEVER called WITHOUT a filter (no fallback)
    unfiltered_calls = [
        c for c in mock_search.call_args_list
        if c.kwargs.get("filter") is None
    ]
    assert len(unfiltered_calls) == 0, (
        f"FALLBACK DETECTED: rag_engine.search was called without a filter {len(unfiltered_calls)} time(s). "
        f"This means the unfiltered fallback is still active. Calls: {unfiltered_calls}"
    )


@pytest.mark.asyncio
async def test_category_filter_no_fallback_deep_mode(client):
    """
    Same test as fast mode, but for non-streaming deep mode (non-fast endpoint).
    
    When domain=law and the category filter returns 0 results, there must be NO fallback
    to unfiltered search.
    """
    def mock_search_side_effect(*args, **kwargs):
        filter_arg = kwargs.get("filter")
        if filter_arg:
            # Filtered search returns empty (simulates no category metadata)
            return []
        else:
            # Unfiltered would return financial docs (should NOT happen)
            return [
                {"text": "Trail Balance data", "score": 0.88, "metadata": {"source": "Trail Balance.xlsx"}}
            ]

    mock_search = AsyncMock(side_effect=mock_search_side_effect)

    with (
        patch("api.chat.classify_domain", new=AsyncMock(return_value=_stub_classify_law())),
        patch("api.chat.get_llm_provider", return_value=_mock_llm()),
        patch("api.chat.rag_engine.search", new=mock_search),
        patch("api.chat.classify_intent", new=AsyncMock(return_value=_stub_intent())),
        patch("api.chat._generate_title", new=AsyncMock()),
    ):
        resp = await client.post(
            "/api/chat/send",
            json={
                "message": "Explain UAE labor law termination procedures",
                "stream": False,  # Non-streaming (deep mode path)
                "mode": "deep_research",
                "domain": "law",
            },
        )

    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
    
    # Verify filtered calls exist
    filtered_calls = [
        c for c in mock_search.call_args_list
        if c.kwargs.get("filter") is not None
    ]
    assert len(filtered_calls) > 0, "Expected at least one filtered search call"
    
    # CRITICAL: No unfiltered fallback
    unfiltered_calls = [
        c for c in mock_search.call_args_list
        if c.kwargs.get("filter") is None
    ]
    assert len(unfiltered_calls) == 0, (
        f"FALLBACK DETECTED in deep mode: unfiltered search called {len(unfiltered_calls)} time(s). "
        f"Calls: {unfiltered_calls}"
    )


@pytest.mark.asyncio
async def test_doc_scoped_filter_still_works(client):
    """
    When selected_doc_ids is provided, the doc_id filter IS used, and no fallback happens.
    This ensures we didn't break the doc-scoped filtering path.
    
    Doc-scoped queries should:
    1. Use {"doc_id": {"$in": [...]}} filter
    2. NOT trigger category/domain filter
    3. NOT trigger any fallback (even if results are empty, which is valid when user picked wrong docs)
    """
    mock_search = AsyncMock(return_value=[
        {"text": "Relevant doc content", "score": 0.92, "metadata": {"source": "selected-doc.pdf", "doc_id": "doc-123"}}
    ])

    with (
        patch("api.chat.classify_domain", new=AsyncMock(return_value=_stub_classify_finance())),
        patch("api.chat.get_llm_provider", return_value=_mock_llm()),
        patch("api.chat.rag_engine.search", new=mock_search),
        patch("api.chat.classify_intent", new=AsyncMock(return_value=_stub_intent())),
        patch("api.chat._generate_title", new=AsyncMock()),
    ):
        resp = await client.post(
            "/api/chat/send",
            json={
                "message": "What is the VAT rate?",
                "stream": False,
                "selected_doc_ids": ["doc-123", "doc-456"],
                "domain": "vat",
            },
        )

    assert resp.status_code == 200
    assert mock_search.called, "rag_engine.search was never called"
    
    # Verify doc_id filter was used
    doc_id_filter_calls = [
        c for c in mock_search.call_args_list
        if c.kwargs.get("filter") == {"doc_id": {"$in": ["doc-123", "doc-456"]}}
    ]
    assert len(doc_id_filter_calls) > 0, (
        f"Expected doc_id filter to be used. Calls: {mock_search.call_args_list}"
    )
    
    # Verify NO calls were made with category filter (doc-scoped bypasses category)
    category_filter_calls = [
        c for c in mock_search.call_args_list
        if isinstance(c.kwargs.get("filter"), dict) and "category" in c.kwargs.get("filter", {})
    ]
    assert len(category_filter_calls) == 0, (
        "Doc-scoped query should not use category filter"
    )
    
    # Verify NO unfiltered calls (no fallback)
    unfiltered_calls = [
        c for c in mock_search.call_args_list
        if c.kwargs.get("filter") is None
    ]
    assert len(unfiltered_calls) == 0, (
        f"Unfiltered fallback should not happen for doc-scoped queries. Calls: {unfiltered_calls}"
    )
