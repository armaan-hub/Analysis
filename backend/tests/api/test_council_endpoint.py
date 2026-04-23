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


@pytest.mark.asyncio
async def test_empty_question_returns_422(client):
    r = await client.post("/api/chat/council", json={
        "question": "",
        "base_answer": "Yes per IFRS 16",
    })
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_invalid_provider_returns_400(client):
    r = await client.post("/api/chat/council", json={
        "question": "Is this a lease?",
        "base_answer": "Yes",
        "provider": "nonexistent_llm_xyz",
    })
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_llm_error_emits_error_events(client, monkeypatch):
    class _BrokenLLM:
        async def stream(self, prompt, **kw):
            if False:
                yield
            raise RuntimeError("LLM offline")

    monkeypatch.setattr("api.council.get_llm_provider", lambda *a, **kw: _BrokenLLM())
    r = await client.post("/api/chat/council", json={
        "question": "Is this a lease?",
        "base_answer": "Yes",
    })
    assert r.status_code == 200
    assert "council_error" in r.text
    assert "done" in r.text
