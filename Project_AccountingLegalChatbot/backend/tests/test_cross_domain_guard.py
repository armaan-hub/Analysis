"""
Tests for cross-domain RAG source suppression.

When a domain-specific query (e.g., corporate_tax) triggers the broad fallback and
the fallback returns documents from a different domain (e.g., vat), the guard must
clear the results so the LLM does not receive misleading context.
"""
import json
import pytest
from unittest.mock import AsyncMock, patch, MagicMock


def _make_classifier(domain: str, confidence: float = 0.85):
    """Create a minimal ClassifierResult-like object."""
    from core.chat.domain_classifier import DomainLabel, ClassifierResult
    return ClassifierResult(domain=DomainLabel(domain), confidence=confidence, alternatives=[])


def _make_llm_mock():
    """Return a mock LLM provider."""
    m = MagicMock()
    m.compute_safe_max_tokens = MagicMock(return_value=4096)
    m.chat = AsyncMock(return_value=MagicMock(
        content="Corporate tax answer.", tokens_used=50, provider="mock", model="mock-v1"
    ))

    async def _stream_impl(*a, **kw):
        yield "Corporate tax answer."

    m.chat_stream = MagicMock(side_effect=_stream_impl)
    m._last_stream_tokens = 0
    return m


def _vat_result(score: float = 0.68) -> dict:
    return {
        "id": "chunk-vat-001",
        "text": "VAT real estate content.",
        "score": score,
        "combined_score": score,
        "metadata": {
            "source": "UAE-VAT-REAL-ESTATE-FAQ.pdf",
            "original_name": "UAE VAT Real Estate FAQ.pdf",
            "page": 1,
            "domain": "vat",
            "category": "finance",
        },
    }


def _corp_tax_result(score: float = 0.72) -> dict:
    return {
        "id": "chunk-ct-001",
        "text": "Corporate tax rate is 9%.",
        "score": score,
        "combined_score": score,
        "metadata": {
            "source": "UAE-Corporate-Tax-Guide.pdf",
            "original_name": "UAE Corporate Tax Guide.pdf",
            "page": 1,
            "domain": "corporate_tax",
            "category": "finance",
        },
    }


@pytest.mark.asyncio
async def test_cross_domain_full_suppression_non_streaming(client):
    """Non-streaming: all-VAT broad-fallback results for corporate_tax query must be cleared."""
    with (
        patch("api.chat.classify_domain", new=AsyncMock(return_value=_make_classifier("corporate_tax"))),
        patch("api.chat.get_llm_provider", return_value=_make_llm_mock()),
        patch("api.chat._hybrid_retriever.retrieve", new=AsyncMock(return_value=[])),
        patch("api.chat.rag_engine.search", new=AsyncMock(return_value=[_vat_result()])),
        patch("api.chat.search_web", new=AsyncMock(return_value=[])),
    ):
        resp = await client.post(
            "/api/chat/send",
            json={"message": "tell me corporate tax", "stream": False, "use_rag": True},
        )

    assert resp.status_code == 200
    data = resp.json()
    sources = (data.get("message") or {}).get("sources") or []
    vat_sources = [s for s in sources if (s.get("metadata") or s).get("domain") == "vat"]
    assert not vat_sources, f"VAT sources leaked into corporate_tax response: {vat_sources}"


@pytest.mark.asyncio
async def test_cross_domain_partial_filter_non_streaming(client):
    """Non-streaming: mixed results → only corporate_tax kept, vat filtered out."""
    with (
        patch("api.chat.classify_domain", new=AsyncMock(return_value=_make_classifier("corporate_tax"))),
        patch("api.chat.get_llm_provider", return_value=_make_llm_mock()),
        patch("api.chat._hybrid_retriever.retrieve", new=AsyncMock(return_value=[])),
        patch("api.chat.rag_engine.search", new=AsyncMock(return_value=[_corp_tax_result(0.72), _vat_result(0.68)])),
        patch("api.chat.search_web", new=AsyncMock(return_value=[])),
    ):
        resp = await client.post(
            "/api/chat/send",
            json={"message": "corporate tax rates UAE", "stream": False, "use_rag": True},
        )

    assert resp.status_code == 200
    data = resp.json()
    sources = (data.get("message") or {}).get("sources") or []
    src_domains = {(s.get("metadata") or s).get("domain") for s in sources}
    assert "vat" not in src_domains, "VAT sources should be filtered"
    assert "corporate_tax" in src_domains, "corporate_tax sources should remain"


@pytest.mark.asyncio
async def test_cross_domain_partial_filter_streaming(client):
    """Streaming: mixed corporate_tax + vat broad-fallback results → vat filtered, corp_tax kept."""
    mock_llm = _make_llm_mock()
    mixed_results = [_corp_tax_result(0.72), _vat_result(0.68)]

    with (
        patch("api.chat.classify_domain", new=AsyncMock(return_value=_make_classifier("corporate_tax"))),
        patch("api.chat.get_llm_provider", return_value=mock_llm),
        patch("api.chat._hybrid_retriever.retrieve", new=AsyncMock(return_value=[])),
        patch("api.chat.rag_engine.search", new=AsyncMock(return_value=mixed_results)),
        patch("api.chat.search_web", new=AsyncMock(return_value=[])),
    ):
        resp = await client.post(
            "/api/chat/send",
            json={"message": "corporate tax rates UAE", "stream": True, "use_rag": True},
        )

    assert resp.status_code == 200

    # With partial filter: corporate_tax doc kept, vat doc dropped
    # Streaming serializes sources as flat dicts with top-level "domain" key
    for line in resp.text.split("\n"):
        if line.startswith("data:"):
            try:
                data = json.loads(line[5:])
                if data.get("type") == "sources":
                    src_domains = {s.get("domain") for s in data.get("sources", [])}
                    assert "vat" not in src_domains, f"VAT sources should have been filtered: {data['sources']}"
                    assert "corporate_tax" in src_domains, f"corporate_tax sources should be kept: {data['sources']}"
            except json.JSONDecodeError:
                pass

    # Verify LLM was called without VAT content in context
    all_calls = list(mock_llm.chat_stream.call_args_list) + list(mock_llm.chat.call_args_list)
    for call in all_calls:
        args = call[0] if call[0] else []
        kwargs = call[1] if call[1] else {}
        messages = args[0] if args else kwargs.get("messages", [])
        for msg in messages:
            content = msg.get("content", "")
            assert "VAT real estate" not in content, \
                f"VAT content leaked into LLM messages: {content[:200]}"


@pytest.mark.asyncio
async def test_cross_domain_suppression_streaming(client):
    """Streaming: all-VAT broad-fallback results for corporate_tax query must be cleared."""
    mock_llm = _make_llm_mock()
    with (
        patch("api.chat.classify_domain", new=AsyncMock(return_value=_make_classifier("corporate_tax"))),
        patch("api.chat.get_llm_provider", return_value=mock_llm),
        patch("api.chat._hybrid_retriever.retrieve", new=AsyncMock(return_value=[])),
        patch("api.chat.rag_engine.search", new=AsyncMock(return_value=[_vat_result()])),
        patch("api.chat.search_web", new=AsyncMock(return_value=[])),
    ):
        resp = await client.post(
            "/api/chat/send",
            json={"message": "tell me corporate tax", "stream": True, "use_rag": True},
        )

    assert resp.status_code == 200

    # If guard worked, no sources event is emitted (results cleared)
    # If guard failed, sources event fires with VAT sources
    for line in resp.text.split("\n"):
        if line.startswith("data:"):
            try:
                data = json.loads(line[5:])
                if data.get("type") == "sources":
                    src_domains = {s.get("domain") for s in data.get("sources", [])}
                    assert "vat" not in src_domains, f"VAT sources leaked: {data['sources']}"
            except json.JSONDecodeError:
                pass

    # Verify LLM was called without VAT context in the messages
    assert mock_llm.chat_stream.call_count >= 1 or mock_llm.chat.call_count >= 1, \
        "LLM must have been called"
    # Check the messages passed to LLM don't contain VAT real estate text
    all_calls = list(mock_llm.chat_stream.call_args_list) + list(mock_llm.chat.call_args_list)
    for call in all_calls:
        args = call[0] if call[0] else []
        kwargs = call[1] if call[1] else {}
        messages = args[0] if args else kwargs.get("messages", [])
        for msg in messages:
            content = msg.get("content", "")
            assert "VAT real estate" not in content, \
                f"VAT real estate content leaked into LLM messages: {content[:200]}"


@pytest.mark.asyncio
async def test_general_law_not_affected_by_guard(client):
    """general_law queries: cross-domain guard must not fire; sources above threshold must survive."""
    with (
        patch("api.chat.classify_domain", new=AsyncMock(return_value=_make_classifier("general_law", 0.95))),
        patch("api.chat.get_llm_provider", return_value=_make_llm_mock()),
        patch("api.chat._hybrid_retriever.retrieve", new=AsyncMock(return_value=[_vat_result(0.45)])),
    ):
        resp = await client.post(
            "/api/chat/send",
            json={"message": "draft a will for my estate", "stream": False, "use_rag": True},
        )
    assert resp.status_code == 200
    data = resp.json()
    sources = (data.get("message") or {}).get("sources") or []
    # general_law has no entry in _DOMAIN_TO_DOC_DOMAINS → guard must not fire
    # Source with score 0.45 is above _GENERAL_LAW_MIN_RELEVANCE_SCORE (0.35) → must survive
    assert sources, "Sources above relevance threshold must not be suppressed for general_law queries"
