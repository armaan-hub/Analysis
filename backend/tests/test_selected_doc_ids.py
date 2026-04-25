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
    """When selected_doc_ids is provided in non-analyst mode, rag_engine.search must be called
    with $and filter combining doc_id scope and law+finance category to prevent workbook contamination."""
    mock_search = AsyncMock(return_value=[
        {"text": "stub chunk", "score": 0.9, "metadata": {"source": "test.pdf"}}
    ])

    with (
        patch("api.chat.classify_domain", new=AsyncMock(return_value=_stub_cls())),
        patch("api.chat.get_llm_provider", return_value=_mock_llm()),
        patch("api.chat.rag_engine.search", new=mock_search),
        patch("api.chat.classify_intent", new=AsyncMock(
            return_value=type("I", (), {"output_type": "answer", "topic": "vat"})()
        )),
        patch("api.chat._generate_title", new=AsyncMock()),
    ):
        resp = await client.post(
            "/api/chat/send",
            json={
                "message": "What is VAT rate?",
                "stream": False,
                "mode": "fast",
                "selected_doc_ids": ["doc-aaa", "doc-bbb"],
            },
        )

    expected_filter = {
        "$and": [
            {"doc_id": {"$in": ["doc-aaa", "doc-bbb"]}},
            {"category": {"$in": ["law", "finance"]}},
        ]
    }
    assert resp.status_code == 200
    assert mock_search.called, "rag_engine.search was never called"
    filter_args = [c.kwargs.get("filter") for c in mock_search.call_args_list]
    assert any(
        f == expected_filter for f in filter_args
    ), f"No call with correct $and filter. Calls: {mock_search.call_args_list}"
    # No call should be made without the doc_id filter (fallback must not fire)
    unfiltered_calls = [
        c for c in mock_search.call_args_list
        if c.kwargs.get("filter") != expected_filter
    ]
    assert not unfiltered_calls, (
        f"Unfiltered (fallback) RAG calls occurred: {unfiltered_calls}"
    )


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
        patch("api.chat._generate_title", new=AsyncMock()),
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
