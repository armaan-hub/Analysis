import pytest
import json


@pytest.mark.asyncio
async def test_financial_council_stream_endpoint(client, monkeypatch):
    class _StubLLM:
        async def chat_stream(self, messages, **kw):
            yield "Report chunk data"

    monkeypatch.setattr("api.council.get_llm_provider", lambda *a, **kw: _StubLLM())
    r = await client.post("/api/chat/financial-council", json={
        "doc1_balance_sheet": "Sample BS",
        "doc2_profit_loss": "Sample PL",
        "doc3_corporate_legal": "Sample Legal",
        "doc4_template_notes": "Sample Notes",
    })
    assert r.status_code == 200
    text = r.text
    assert "audit_council_agent_start" in text
    assert "legal_extraction" in text
    assert "math_qc" in text
    assert "audit_council_done" in text


@pytest.mark.asyncio
async def test_financial_council_sync_endpoint(client, monkeypatch):
    class _StubLLM:
        async def chat_stream(self, messages, **kw):
            yield "# Full Synthetic Mainland Audit Report"

    monkeypatch.setattr("api.council.get_llm_provider", lambda *a, **kw: _StubLLM())
    r = await client.post("/api/chat/financial-council/sync", json={
        "doc1_balance_sheet": "Sample BS",
        "doc2_profit_loss": "Sample PL",
        "doc3_corporate_legal": "Sample Legal",
        "doc4_template_notes": "Sample Notes",
    })
    assert r.status_code == 200
    data = r.json()
    assert data["success"] is True
    assert "report_markdown" in data
    assert "qc_critique" in data
    assert len(data["stage_outputs"]) == 6


@pytest.mark.asyncio
async def test_financial_council_invalid_provider_returns_400(client):
    r = await client.post("/api/chat/financial-council", json={
        "doc1_balance_sheet": "Sample BS",
        "provider": "nonexistent_llm_xyz",
    })
    assert r.status_code == 400
