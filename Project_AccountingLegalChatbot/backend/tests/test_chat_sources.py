"""Tests that source names in chat responses use original_name, not UUID hash filenames."""
import pytest
from unittest.mock import AsyncMock, patch
from core.chat.domain_classifier import DomainLabel, ClassifierResult
from core.llm_manager import LLMResponse


def _stub_classifier():
    return ClassifierResult(domain=DomainLabel.GENERAL_LAW, confidence=0.9, alternatives=[])


def _mock_llm():
    mock = AsyncMock()
    mock.chat = AsyncMock(
        return_value=LLMResponse(
            content="VAT is 5%.", tokens_used=10, provider="mock", model="mock-v1"
        )
    )

    async def _fake_stream(*a, **kw):
        yield "VAT is 5%."

    mock.chat_stream = _fake_stream
    return mock


RAG_RESULT = [
    {
        "text": "VAT rate is 5% on most goods.",
        "metadata": {
            "source": "a1b2c3d4_vat_guide.pdf",
            "original_name": "UAE VAT Guide 2024.pdf",
            "page": 3,
            "doc_id": "doc-001",
        },
        "score": 0.92,
    }
]


@pytest.mark.asyncio
async def test_sources_use_original_name_not_uuid(client):
    """Source names in the chat response must be original_name, not UUID-prefixed filename."""
    with (
        patch("api.chat.classify_domain", new=AsyncMock(return_value=_stub_classifier())),
        patch("api.chat.get_llm_provider", return_value=_mock_llm()),
        patch("api.chat.rag_engine.search", new=AsyncMock(return_value=RAG_RESULT)),
    ):
        resp = await client.post(
            "/api/chat/send",
            json={"message": "What is UAE VAT rate?", "use_rag": True, "stream": False},
        )
    assert resp.status_code == 200
    sources = resp.json()["message"]["sources"]
    assert sources, "Expected at least one source"
    assert sources[0]["source"] == "UAE VAT Guide 2024.pdf", (
        f"Expected original_name, got: {sources[0]['source']}"
    )
    assert "a1b2c3d4" not in sources[0]["source"]
