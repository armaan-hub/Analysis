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
    try:
        from core.chat.domain_classifier import DomainLabel, ClassifierResult
        return ClassifierResult(domain=DomainLabel(domain), confidence=confidence, alternatives=[])
    except Exception:
        # Fallback minimal mock
        r = MagicMock()
        r.domain.value = domain
        r.confidence = confidence
        return r


def _make_llm_mock():
    """Return a mock LLM provider."""
    m = MagicMock()
    m.compute_safe_max_tokens = MagicMock(return_value=4096)
    m.chat = AsyncMock(return_value=MagicMock(
        content="Corporate tax answer.", tokens_used=50, provider="mock", model="mock-v1"
    ))

    async def _stream(*a, **kw):
        yield "Corporate tax answer."

    m.chat_stream = _stream
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
async def test_cross_domain_suppression_streaming(client):
    """Streaming: all-VAT broad-fallback results for corporate_tax query must be cleared."""
    with (
        patch("api.chat.classify_domain", new=AsyncMock(return_value=_make_classifier("corporate_tax"))),
        patch("api.chat.get_llm_provider", return_value=_make_llm_mock()),
        patch("api.chat._hybrid_retriever.retrieve", new=AsyncMock(return_value=[])),
        patch("api.chat.rag_engine.search", new=AsyncMock(return_value=[_vat_result()])),
        patch("api.chat.search_web", new=AsyncMock(return_value=[])),
    ):
        resp = await client.post(
            "/api/chat/send",
            json={"message": "tell me corporate tax", "stream": True, "use_rag": True},
        )

    assert resp.status_code == 200
    for line in resp.text.split("\n"):
        if line.startswith("data:"):
            try:
                data = json.loads(line[5:])
                if data.get("type") == "sources":
                    src_domains = {s.get("domain") for s in data.get("sources", [])}
                    assert "vat" not in src_domains, f"VAT sources leaked: {data['sources']}"
            except json.JSONDecodeError:
                pass


@pytest.mark.asyncio
async def test_general_law_not_affected_by_guard(client):
    """general_law queries must NOT be affected by the cross-domain guard."""
    # general_law has no entry in _DOMAIN_TO_DOC_DOMAINS — guard must not fire
    with (
        patch("api.chat.classify_domain", new=AsyncMock(return_value=_make_classifier("general_law", 0.95))),
        patch("api.chat.get_llm_provider", return_value=_make_llm_mock()),
        patch("api.chat._hybrid_retriever.retrieve", new=AsyncMock(return_value=[_vat_result(0.45)])),
    ):
        resp = await client.post(
            "/api/chat/send",
            json={"message": "draft a will for my estate", "stream": False, "use_rag": True},
        )
    # Should not crash and should return 200 (guard doesn't interfere)
    assert resp.status_code == 200
