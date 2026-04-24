"""Verify that the streaming path yields the meta SSE event before
any chunk events, proving classify_domain runs inside generate()."""
import json
import pytest
from unittest.mock import AsyncMock, patch
from core.chat.domain_classifier import DomainLabel, ClassifierResult
from core.llm_manager import LLMResponse


def _stub_cls():
    return ClassifierResult(domain=DomainLabel.VAT, confidence=0.9, alternatives=[])


def _mock_llm():
    m = AsyncMock()
    m.chat = AsyncMock(
        return_value=LLMResponse(content="VAT answer", tokens_used=10, provider="mock", model="m")
    )

    async def _stream(*a, **kw):
        yield "VAT answer"

    m.chat_stream = _stream
    return m


def _parse_sse(raw: bytes) -> list[dict]:
    events = []
    for frame in raw.decode().split("\n\n"):
        frame = frame.strip()
        if frame.startswith("data: "):
            try:
                events.append(json.loads(frame[6:]))
            except json.JSONDecodeError:
                pass
    return events


@pytest.mark.asyncio
async def test_streaming_yields_meta_before_chunks(client):
    """First SSE event must be type='meta' with conversation_id and detected_domain."""
    with (
        patch("api.chat.classify_domain", new=AsyncMock(return_value=_stub_cls())),
        patch("api.chat.get_llm_provider", return_value=_mock_llm()),
        patch("api.chat.rag_engine.search", new=AsyncMock(return_value=[])),
        patch("api.chat.classify_intent", new=AsyncMock(
            return_value=type("I", (), {"output_type": "answer", "topic": "vat"})()
        )),
        patch("api.chat._get_query_variations", new=AsyncMock(return_value=["What is VAT?"])),
        patch("api.chat.search_web", new=AsyncMock(return_value=[])),
    ):
        resp = await client.post(
            "/api/chat/send",
            json={"message": "What is UAE VAT?", "stream": True, "mode": "fast"},
        )

    assert resp.status_code == 200, resp.text
    events = _parse_sse(resp.content)
    assert events, "No SSE events received"
    assert events[0]["type"] == "meta", f"First event must be meta, got: {events[0]}"
    assert "conversation_id" in events[0], "meta missing conversation_id"
    assert "detected_domain" in events[0], "meta missing detected_domain"


@pytest.mark.asyncio
async def test_streaming_meta_contains_correct_domain(client):
    """meta event's detected_domain must match what classify_domain returned."""
    with (
        patch("api.chat.classify_domain", new=AsyncMock(return_value=_stub_cls())),
        patch("api.chat.get_llm_provider", return_value=_mock_llm()),
        patch("api.chat.rag_engine.search", new=AsyncMock(return_value=[])),
        patch("api.chat.classify_intent", new=AsyncMock(
            return_value=type("I", (), {"output_type": "answer", "topic": "vat"})()
        )),
        patch("api.chat._get_query_variations", new=AsyncMock(return_value=["What is VAT?"])),
        patch("api.chat.search_web", new=AsyncMock(return_value=[])),
    ):
        resp = await client.post(
            "/api/chat/send",
            json={"message": "What is UAE VAT?", "stream": True, "mode": "fast"},
        )

    events = _parse_sse(resp.content)
    meta = next((e for e in events if e.get("type") == "meta"), None)
    assert meta is not None, "No meta event found"
    assert meta["detected_domain"] == "vat", f"Expected 'vat', got: {meta['detected_domain']}"
