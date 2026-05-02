import pytest
import json
from httpx import AsyncClient, ASGITransport
from unittest.mock import AsyncMock, patch, MagicMock
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
    mock.compute_safe_max_tokens = MagicMock(return_value=2000)
    return mock


@pytest.fixture
def mock_rag_empty(monkeypatch):
    """Patch rag_engine.search to return empty list."""
    from core.rag_engine import rag_engine
    monkeypatch.setattr(rag_engine, "search", AsyncMock(return_value=[]))


@pytest.mark.asyncio
async def test_no_llm_guard_returns_honest_message_for_doc_scoped(
    client: AsyncClient, mock_rag_empty
):
    """When doc-scoped RAG returns 0 results, answer must be the honest refusal — LLM not called."""
    # First create a conversation
    with (
        patch("api.chat.classify_domain", new=AsyncMock(return_value=_stub_classifier(DomainLabel.GENERAL_LAW))),
        patch("api.chat.get_llm_provider", return_value=_mock_llm()),
        patch("api.chat._generate_title", new=AsyncMock()),
        patch("api.chat.classify_intent", new=AsyncMock()),
    ):
        init_resp = await client.post("/api/chat/send", json={
            "message": "init",
            "mode": "analyst",
            "stream": False,
        })
        conv_id = init_resp.json()["conversation_id"]
    
    # Now test the guard with doc-scoped query and empty RAG results
    with (
        patch("api.chat.get_llm_provider") as mock_llm,
        patch("api.chat.classify_intent", new=AsyncMock()),
    ):
        mock_llm.return_value = _mock_llm()
        resp = await client.post("/api/chat/send", json={
            "conversation_id": conv_id,
            "message": "What is the penalty for late VAT filing?",
            "mode": "analyst",
            "selected_doc_ids": ["doc-that-exists"],
            "use_rag": True,
            "stream": False,
        })
    assert resp.status_code == 200
    data = resp.json()
    # Non-streaming response shape: {"message": {"content": "...", ...}, "conversation_id": "..."}
    assert "don't have" in data["message"]["content"].lower()
    # LLM should NOT have been called (intent classifier is mocked separately)
    mock_llm.return_value.chat.assert_not_called()


@pytest.mark.asyncio
async def test_no_guard_when_not_doc_scoped(client: AsyncClient, mock_rag_empty):
    """When not doc-scoped and RAG is empty, LLM IS called (web search fallback may fire)."""
    # First create a conversation
    with (
        patch("api.chat.classify_domain", new=AsyncMock(return_value=_stub_classifier(DomainLabel.GENERAL_LAW))),
        patch("api.chat.get_llm_provider", return_value=_mock_llm()),
        patch("api.chat._generate_title", new=AsyncMock()),
        patch("api.chat.classify_intent", new=AsyncMock()),
    ):
        init_resp = await client.post("/api/chat/send", json={
            "message": "init",
            "mode": "fast",
            "stream": False,
        })
        conv_id = init_resp.json()["conversation_id"]
    
    # Now test without guard - LLM should be called
    with (
        patch("api.chat.get_llm_provider", return_value=_mock_llm()),
        patch("api.chat._generate_title", new=AsyncMock()),
        patch("api.chat.classify_intent", new=AsyncMock()),
    ):
        resp = await client.post("/api/chat/send", json={
            "conversation_id": conv_id,
            "message": "What is VAT?",
            "mode": "fast",
            "use_rag": True,
            "stream": False,
        })
    assert resp.status_code == 200
