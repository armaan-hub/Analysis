import json
import pytest
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient
from main import app


async def _fake_events(**_):
    yield {"type": "step", "text": "Analyzing query..."}
    yield {"type": "answer", "content": "done", "sources": [], "web_sources": []}
    yield {"type": "done"}


def test_deep_research_streams_sse():
    client = TestClient(app)
    with patch("api.research.run_deep_research", _fake_events):
        with client.stream(
            "POST",
            "/api/chat/deep-research",
            json={"conversation_id": "c1", "query": "q", "selected_doc_ids": []},
        ) as r:
            assert r.status_code == 200
            assert r.headers["content-type"].startswith("text/event-stream")
            body = b"".join(r.iter_bytes()).decode()

    # every frame starts with "data: " and is parseable JSON
    frames = [line[len("data: "):] for line in body.splitlines() if line.startswith("data: ")]
    parsed = [json.loads(f) for f in frames]
    types = [p["type"] for p in parsed]
    assert types == ["step", "answer", "done"]
