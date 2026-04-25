"""Tests for multi-query RAG in fast mode."""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from api.chat import _get_query_variations
from core.llm_manager import LLMResponse
from core.chat.domain_classifier import DomainLabel, ClassifierResult


def _stub_classifier():
    return ClassifierResult(domain=DomainLabel.GENERAL_LAW, confidence=0.9, alternatives=[])


def _mock_llm(answer: str = "Answer."):
    mock = MagicMock()
    mock.chat = AsyncMock(
        return_value=LLMResponse(content=answer, tokens_used=10, provider="mock", model="mock-v1")
    )
    async def _stream(*a, **kw):
        yield answer
    mock.chat_stream = _stream
    return mock


@pytest.mark.asyncio
async def test_get_query_variations_returns_list_with_original():
    """_get_query_variations must always include the original query first."""
    mock_llm = _mock_llm('["What is UAE VAT?", "UAE value added tax rate"]')
    with patch("api.chat.get_llm_provider", return_value=mock_llm):
        result = await _get_query_variations("UAE VAT rate")
    assert result[0] == "UAE VAT rate", "Original query must be first"
    assert len(result) >= 1


@pytest.mark.asyncio
async def test_get_query_variations_falls_back_on_error():
    """_get_query_variations must return [original] when LLM fails."""
    mock = MagicMock()
    mock.chat = AsyncMock(side_effect=Exception("LLM timeout"))
    with patch("api.chat.get_llm_provider", return_value=mock):
        result = await _get_query_variations("UAE VAT rate")
    assert result == ["UAE VAT rate"]


@pytest.mark.asyncio
async def test_fast_mode_calls_rag_multiple_times(client):
    """Fast mode send must call rag_engine.search for each query variation."""
    search_mock = AsyncMock(return_value=[])

    with (
        patch("api.chat.classify_domain", new=AsyncMock(return_value=_stub_classifier())),
        patch("api.chat.get_llm_provider", return_value=_mock_llm()),
        patch("api.chat.rag_engine.search", search_mock),
        patch("api.chat._get_query_variations", new=AsyncMock(return_value=["q1", "q2", "q3"])),
        patch("api.chat._generate_title", new=AsyncMock()),
    ):
        resp = await client.post(
            "/api/chat/send",
            json={"message": "UAE VAT rate?", "use_rag": True, "mode": "fast", "stream": False},
        )
    assert resp.status_code == 200
    assert search_mock.call_count >= 2, (
        f"Expected multiple RAG calls in fast mode, got {search_mock.call_count}"
    )
