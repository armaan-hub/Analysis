"""Verify that selected_doc_ids in the chat request restricts the RAG filter."""
import pytest
from unittest.mock import AsyncMock, patch
from core.chat.domain_classifier import DomainLabel, ClassifierResult
from core.llm_manager import LLMResponse


def _stub_cls():
    return ClassifierResult(domain=DomainLabel.VAT, confidence=0.9, alternatives=[])


def _mock_llm():
    m = AsyncMock()
    m.chat = AsyncMock(
        return_value=LLMResponse(content="ok", tokens_used=5, provider="mock", model="m")
    )

    async def _stream(*a, **kw):
        yield "ok"

    m.chat_stream = _stream
    return m


@pytest.mark.asyncio
async def test_selected_doc_ids_scopes_rag_filter(client):
    """When selected_doc_ids is provided, rag_engine.search must be called
    with filter={'doc_id': {'$in': selected_doc_ids}}."""
    mock_search = AsyncMock(return_value=[])

    with (
        patch("api.chat.classify_domain", new=AsyncMock(return_value=_stub_cls())),
        patch("api.chat.get_llm_provider", return_value=_mock_llm()),
        patch("api.chat.rag_engine.search", new=mock_search),
        patch("api.chat.classify_intent", new=AsyncMock(
            return_value=type("I", (), {"output_type": "answer", "topic": "vat"})()
        )),
    ):
        resp = await client.post(
            "/api/chat/send",
            json={
                "message": "What is VAT rate?",
                "stream": False,
                "selected_doc_ids": ["doc-aaa", "doc-bbb"],
            },
        )

    assert resp.status_code == 200
    assert mock_search.called, "rag_engine.search was never called"
    filter_args = [c.kwargs.get("filter") for c in mock_search.call_args_list]
    assert any(
        f == {"doc_id": {"$in": ["doc-aaa", "doc-bbb"]}} for f in filter_args
    ), f"No call with correct doc_id filter. Calls: {mock_search.call_args_list}"


@pytest.mark.asyncio
async def test_no_selected_doc_ids_uses_domain_filter(client):
    """When selected_doc_ids is absent, rag_engine.search should NOT use a doc_id filter."""
    mock_search = AsyncMock(return_value=[])

    with (
        patch("api.chat.classify_domain", new=AsyncMock(return_value=_stub_cls())),
        patch("api.chat.get_llm_provider", return_value=_mock_llm()),
        patch("api.chat.rag_engine.search", new=mock_search),
        patch("api.chat.classify_intent", new=AsyncMock(
            return_value=type("I", (), {"output_type": "answer", "topic": "vat"})()
        )),
    ):
        resp = await client.post(
            "/api/chat/send",
            json={"message": "What is VAT rate?", "stream": False},
        )

    assert resp.status_code == 200
    filter_args = [c.kwargs.get("filter") for c in mock_search.call_args_list]
    assert not any(
        isinstance(f, dict) and "doc_id" in f for f in filter_args
    ), "unexpected doc_id filter when selected_doc_ids was not set"
