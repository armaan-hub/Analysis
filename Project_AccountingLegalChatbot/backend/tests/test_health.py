"""
Smoke tests — verify the server starts and core endpoints respond.
"""
import pytest


@pytest.mark.asyncio
async def test_root_ok(client):
    resp = await client.get("/")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "running"
    assert "endpoints" in data


@pytest.mark.asyncio
async def test_health_ok(client):
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_documents_list_empty(client):
    resp = await client.get("/api/documents/")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio
async def test_documents_stats(client):
    resp = await client.get("/api/documents/stats")
    assert resp.status_code == 200
    data = resp.json()
    assert "total_documents" in data
    assert "indexed_documents" in data
    assert "total_chunks" in data


@pytest.mark.asyncio
async def test_chat_conversations_empty(client):
    resp = await client.get("/api/chat/conversations")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio
async def test_settings_current(client):
    resp = await client.get("/api/settings/current")
    assert resp.status_code == 200
    data = resp.json()
    assert "llm_provider" in data
