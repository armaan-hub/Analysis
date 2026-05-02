import json
import pytest
from unittest.mock import AsyncMock, patch
from httpx import AsyncClient, ASGITransport
from main import app


class _FakeLLM:
    async def chat_stream(self, messages, **kwargs):
        yield "answer chunk"


@pytest.mark.asyncio
async def test_deep_research_streams_sse():
    fake_rag_results = []
    fake_web_results = [
        {"title": "Test Site", "url": "https://example.com", "body": "content"}
    ]

    with (
        patch("core.rag_engine.rag_engine.search", new_callable=AsyncMock, return_value=fake_rag_results),
        patch("core.web_search.deep_search", new_callable=AsyncMock, return_value=fake_web_results),
        patch("api.chat.get_llm_provider", return_value=_FakeLLM()),
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            async with client.stream(
                "POST",
                "/api/chat/deep-research",
                json={"conversation_id": "c1", "query": "q", "selected_doc_ids": []},
            ) as r:
                assert r.status_code == 200
                assert r.headers["content-type"].startswith("text/event-stream")
                body = "".join([chunk async for chunk in r.aiter_text()])

    # every frame starts with "data: " and is parseable JSON
    frames = [line[len("data: "):] for line in body.splitlines() if line.startswith("data: ")]
    parsed = [json.loads(f) for f in frames]
    types = [p["type"] for p in parsed]
    assert "step" in types
    assert "answer" in types
    assert types[-1] == "done"
