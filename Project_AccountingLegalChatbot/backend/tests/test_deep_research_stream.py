"""Tests for deep research SSE streaming — Bug 3 fix."""
import json
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from starlette.testclient import TestClient
from main import app
from core.llm_manager import LLMResponse


def _mock_llm_stream(text: str):
    mock = MagicMock()
    mock.chat = AsyncMock(return_value=LLMResponse(content=text, tokens_used=8, provider="mock", model="mock-v1"))

    async def _stream(*a, **kw):
        for word in text.split():
            yield word + " "

    mock.chat_stream = _stream
    return mock


RAG_HITS = [
    {
        "text": "UAE VAT applies at 5% on standard-rated supplies.",
        "metadata": {"source": "vat.pdf", "original_name": "UAE VAT Guide.pdf", "page": 1, "doc_id": "doc1"},
        "score": 0.95,
    }
]


def test_deep_research_streams_chunks():
    """deep-research endpoint must yield SSE chunk events during synthesis."""
    with (
        patch("api.chat.get_llm_provider", return_value=_mock_llm_stream("VAT is 5 percent.")),
        patch("api.chat.rag_engine.search", new=AsyncMock(return_value=RAG_HITS)),
        patch("core.web_search.deep_search", new=AsyncMock(return_value=[])),
    ):
        client = TestClient(app)
        with client.stream("POST", "/api/chat/deep-research", json={"query": "UAE VAT rate", "selected_doc_ids": []}) as r:
            raw = b"".join(r.iter_bytes()).decode()

    events = [json.loads(line[6:]) for line in raw.splitlines() if line.startswith("data: ")]
    types = [e["type"] for e in events]

    assert "chunk" in types, f"No chunk events found. All event types: {types}"
    answer_events = [e for e in events if e["type"] == "answer"]
    assert answer_events, "No answer event found"
    assert "VAT" in answer_events[0]["content"]


def test_deep_research_uses_text_key_not_document():
    """RAG results must use the 'text' key for document snippets, not 'document'."""
    captured_messages = []

    def _mock_capturing():
        mock = MagicMock()

        async def _stream(*a, messages=None, **kw):
            msgs = a[0] if a else messages
            if msgs:
                captured_messages.extend(msgs)
            yield "Answer here."

        mock.chat_stream = _stream
        return mock

    with (
        patch("api.chat.get_llm_provider", return_value=_mock_capturing()),
        patch("api.chat.rag_engine.search", new=AsyncMock(return_value=RAG_HITS)),
        patch("core.web_search.deep_search", new=AsyncMock(return_value=[])),
    ):
        client = TestClient(app)
        with client.stream("POST", "/api/chat/deep-research", json={"query": "VAT", "selected_doc_ids": []}) as r:
            b"".join(r.iter_bytes())

    assert captured_messages, "LLM was not called"
    user_msg = next((m for m in captured_messages if m["role"] == "user"), None)
    assert user_msg is not None
    assert "VAT applies at 5%" in user_msg["content"], (
        f"Expected RAG text snippet in prompt. Got: {user_msg['content'][:300]}"
    )
