"""Tests for embedding status and switch endpoints."""
import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from httpx import AsyncClient, ASGITransport
from main import app


@pytest.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


@pytest.mark.asyncio
async def test_get_embedding_status_returns_200(client):
    """GET /api/settings/embedding-status returns provider, model, status, count."""
    with patch("api.settings.rag_engine") as mock_rag:
        mock_rag.collection.count.return_value = 1247
        mock_rag.embedding_provider.provider = "nvidia"
        r = await client.get("/api/settings/embedding-status")
    assert r.status_code == 200
    data = r.json()
    assert "provider" in data
    assert "model" in data
    assert "status" in data
    assert "document_count" in data


@pytest.mark.asyncio
async def test_get_embedding_status_green_when_fast(client):
    """Status is 'green' when embedding responds quickly."""
    with patch("api.settings.rag_engine") as mock_rag, \
         patch("api.settings._check_embedding_latency", new_callable=AsyncMock, return_value=2.0):
        mock_rag.collection.count.return_value = 100
        mock_rag.embedding_provider.provider = "nvidia"
        r = await client.get("/api/settings/embedding-status")
    assert r.status_code == 200
    assert r.json()["status"] == "green"


@pytest.mark.asyncio
async def test_get_embedding_status_yellow_when_slow(client):
    with patch("api.settings.rag_engine") as mock_rag, \
         patch("api.settings._check_embedding_latency", new_callable=AsyncMock, return_value=8.0):
        mock_rag.collection.count.return_value = 100
        mock_rag.embedding_provider.provider = "nvidia"
        r = await client.get("/api/settings/embedding-status")
    assert r.json()["status"] == "yellow"


@pytest.mark.asyncio
async def test_get_embedding_status_red_when_error(client):
    with patch("api.settings.rag_engine") as mock_rag, \
         patch("api.settings._check_embedding_latency", new_callable=AsyncMock, side_effect=Exception("timeout")):
        mock_rag.collection.count.return_value = 100
        mock_rag.embedding_provider.provider = "nvidia"
        r = await client.get("/api/settings/embedding-status")
    assert r.json()["status"] == "red"


@pytest.mark.asyncio
async def test_post_embedding_switch_returns_200(client):
    """POST /api/settings/embedding-switch with valid provider returns 200."""
    r = await client.post("/api/settings/embedding-switch", json={"provider": "openai"})
    assert r.status_code in (200, 202)


@pytest.mark.asyncio
async def test_post_embedding_switch_invalid_provider_returns_422(client):
    r = await client.post("/api/settings/embedding-switch", json={"provider": "unknown_provider"})
    assert r.status_code == 422
