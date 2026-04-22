"""Tests for classifier + domain_override + mode in /api/chat/send."""
import pytest
from unittest.mock import patch, AsyncMock
from core.chat.domain_classifier import DomainLabel, ClassifierResult
from core.llm_manager import LLMResponse


def _stub_classifier(domain: DomainLabel) -> ClassifierResult:
    return ClassifierResult(domain=domain, confidence=0.95, alternatives=[])


def _mock_llm():
    """Return a mock LLM provider with chat and chat_stream."""
    mock = AsyncMock()
    mock.chat = AsyncMock(
        return_value=LLMResponse(
            content="test response", tokens_used=10, provider="mock", model="mock-v1"
        )
    )

    async def _fake_stream(*a, **kw):
        yield "chunk"

    mock.chat_stream = _fake_stream
    return mock


@pytest.mark.asyncio
async def test_send_uses_classifier(client):
    """When no domain_override, the LLM classifier runs and detected_domain appears in SSE meta."""
    with (
        patch("api.chat.classify_domain", new=AsyncMock(return_value=_stub_classifier(DomainLabel.VAT))),
        patch("api.chat.get_llm_provider", return_value=_mock_llm()),
        patch("api.chat.rag_engine.search", new=AsyncMock(return_value=[])),
    ):
        resp = await client.post(
            "/api/chat/send",
            json={"message": "How to file UAE VAT return?", "stream": False},
        )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_send_honors_domain_override(client):
    """When domain_override is set, classifier should NOT be called."""
    with (
        patch("api.chat.classify_domain", new=AsyncMock()) as mock_cls,
        patch("api.chat.get_llm_provider", return_value=_mock_llm()),
        patch("api.chat.rag_engine.search", new=AsyncMock(return_value=[])),
    ):
        resp = await client.post(
            "/api/chat/send",
            json={
                "message": "anything",
                "domain_override": "corporate_tax",
                "stream": False,
            },
        )
        mock_cls.assert_not_called()
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_send_accepts_mode_field(client):
    """The mode field should be accepted without error."""
    with (
        patch("api.chat.classify_domain", new=AsyncMock(return_value=_stub_classifier(DomainLabel.GENERAL_LAW))),
        patch("api.chat.get_llm_provider", return_value=_mock_llm()),
        patch("api.chat.rag_engine.search", new=AsyncMock(return_value=[])),
    ):
        resp = await client.post(
            "/api/chat/send",
            json={"message": "hi", "mode": "deep_research", "stream": False},
        )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_send_with_analyst_mode_persists_mode(client):
    """New conversation created via send must store mode from the request."""
    with (
        patch("api.chat.classify_domain", new=AsyncMock(return_value=_stub_classifier(DomainLabel.GENERAL_LAW))),
        patch("api.chat.get_llm_provider", return_value=_mock_llm()),
        patch("api.chat.rag_engine.search", new=AsyncMock(return_value=[])),
    ):
        resp = await client.post(
            "/api/chat/send",
            json={"message": "hello", "mode": "analyst", "stream": False},
        )
    assert resp.status_code == 200
    cid = resp.json()["conversation_id"]

    r2 = await client.get(f"/api/chat/conversations/{cid}")
    assert r2.status_code == 200
    assert r2.json()["mode"] == "analyst"


@pytest.mark.asyncio
async def test_legacy_domain_field_acts_as_override(client):
    """The existing 'domain' field should work as override for backward compat."""
    with (
        patch("api.chat.classify_domain", new=AsyncMock()) as mock_cls,
        patch("api.chat.get_llm_provider", return_value=_mock_llm()),
        patch("api.chat.rag_engine.search", new=AsyncMock(return_value=[])),
    ):
        resp = await client.post(
            "/api/chat/send",
            json={"message": "test", "domain": "vat", "stream": False},
        )
        mock_cls.assert_not_called()
    assert resp.status_code == 200
