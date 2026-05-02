"""Tests for the cross-domain session endpoint."""
import pytest


@pytest.mark.asyncio
async def test_create_session_default(client):
    resp = await client.post("/api/legal-studio/sessions", json={})
    assert resp.status_code == 200
    data = resp.json()
    assert data["domain"] == "finance"
    assert "conversation_id" in data
    assert "handoff" in data["title"].lower() or "finance" in data["title"].lower()


@pytest.mark.asyncio
async def test_create_session_with_context(client):
    resp = await client.post("/api/legal-studio/sessions", json={
        "title": "VAT analysis",
        "domain": "vat",
        "context_summary": "Discussed VAT implications of cross-border services",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["domain"] == "vat"
    assert data["title"] == "VAT analysis"
