import json
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


async def _fake_rag_search(*args, **kwargs):
    return [{"text": "Revenue: AED 1,000,000", "metadata": {"source": "tb.pdf", "page": 1}, "score": 0.9}]


async def _fake_stream(messages, **kwargs):
    for chunk in ["## MIS Report\n", "Revenue: AED 1,000,000\n", "Net Profit: AED 200,000\n"]:
        yield chunk


def test_generate_stream_returns_sse():
    """POST /api/reports/generate-stream must return an SSE text/event-stream."""
    with patch("api.reports.rag_engine") as mock_rag, \
         patch("api.reports.get_llm_provider") as mock_llm_factory:

        mock_rag.search = AsyncMock(side_effect=_fake_rag_search)

        mock_llm = MagicMock()
        mock_llm.chat_stream = _fake_stream
        mock_llm_factory.return_value = mock_llm

        with client.stream(
            "POST",
            "/api/reports/generate-stream",
            json={
                "report_type": "mis",
                "selected_doc_ids": ["doc-1"],
                "entity_name": "ABC Trading LLC",
                "period_end": "31 Dec 2024",
                "auditor_format": "standard",
            },
        ) as r:
            assert r.status_code == 200
            assert r.headers["content-type"].startswith("text/event-stream")
            body = b"".join(r.iter_bytes()).decode()

    frames = [line[len("data: "):] for line in body.splitlines() if line.startswith("data: ")]
    assert len(frames) >= 1
    parsed = [json.loads(f) for f in frames]
    types = [p["type"] for p in parsed]
    assert "chunk" in types
    assert "done" in types
