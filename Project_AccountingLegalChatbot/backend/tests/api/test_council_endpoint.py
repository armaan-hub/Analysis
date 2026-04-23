import pytest
import json


@pytest.mark.asyncio
async def test_council_endpoint_streams_events(client, monkeypatch):
    class _StubLLM:
        async def stream(self, prompt, **kw):
            yield "ok"

    monkeypatch.setattr("api.council.get_llm_provider", lambda *a, **kw: _StubLLM())
    r = await client.post("/api/chat/council", json={
        "question": "Should we capitalize this lease?",
        "base_answer": "Yes per IFRS 16",
    })
    assert r.status_code == 200
    text = r.text
    assert "council_expert" in text
    assert "Senior CA" in text
    assert "council_synthesis" in text
    assert "done" in text
