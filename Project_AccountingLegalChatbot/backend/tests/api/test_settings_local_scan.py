"""Integration tests for local-scan and detect-provider endpoints."""
import pytest
from unittest.mock import AsyncMock, patch
from core.local_scanner import LocalServer


@pytest.mark.asyncio
async def test_get_local_scan_returns_200(client):
    """GET /api/settings/local-scan always returns 200."""
    mock_servers = [
        LocalServer(provider="ollama", base_url="http://localhost:11434",
                    online=True, models=["qwen3.5:35b"], latency_ms=5),
        LocalServer(provider="lmstudio", base_url="http://localhost:1234",
                    online=False, models=[], latency_ms=0),
    ]
    with patch("api.settings.LocalServerScanner") as MockScanner:
        instance = MockScanner.instance.return_value
        instance.scan_all = AsyncMock(return_value=mock_servers)
        instance.get_cache_age_s.return_value = 10
        r = await client.get("/api/settings/local-scan")

    assert r.status_code == 200
    data = r.json()
    assert "servers" in data
    assert len(data["servers"]) == 2
    assert data["servers"][0]["provider"] == "ollama"
    assert data["servers"][0]["online"] is True
    assert "qwen3.5:35b" in data["servers"][0]["models"]


@pytest.mark.asyncio
async def test_get_local_scan_triggers_scan_when_cache_empty(client):
    """When cache is None, GET /api/settings/local-scan triggers scan_all."""
    mock_servers = [
        LocalServer(provider="ollama", base_url="http://localhost:11434",
                    online=False, models=[], latency_ms=0),
    ]
    with patch("api.settings.LocalServerScanner") as MockScanner:
        instance = MockScanner.instance.return_value
        instance.scan_all = AsyncMock(return_value=mock_servers)
        instance.get_cache_age_s.return_value = 0
        r = await client.get("/api/settings/local-scan")

    assert r.status_code == 200
    data = r.json()
    assert data["servers"][0]["provider"] == "ollama"
    instance.scan_all.assert_called_once()


@pytest.mark.asyncio
async def test_post_local_scan_refresh(client):
    """POST /api/settings/local-scan/refresh triggers force=True scan."""
    mock_servers = [
        LocalServer(provider="ollama", base_url="http://localhost:11434",
                    online=True, models=["new-model"], latency_ms=3),
    ]
    with patch("api.settings.LocalServerScanner") as MockScanner:
        instance = MockScanner.instance.return_value
        instance.scan_all = AsyncMock(return_value=mock_servers)
        r = await client.post("/api/settings/local-scan/refresh")

    assert r.status_code == 200
    data = r.json()
    assert data["servers"][0]["online"] is True
    instance.scan_all.assert_called_once_with(force=True)


@pytest.mark.asyncio
async def test_detect_provider_openai(client):
    r = await client.post("/api/settings/detect-provider",
                          json={"base_url": "https://api.openai.com/v1"})
    assert r.status_code == 200
    data = r.json()
    assert data["provider"] == "openai"
    assert data["key_env_var"] == "OPENAI_API_KEY"
    assert data["key_valid"] is False  # no key provided


@pytest.mark.asyncio
async def test_detect_provider_ollama(client):
    r = await client.post("/api/settings/detect-provider",
                          json={"base_url": "http://localhost:11434"})
    assert r.status_code == 200
    data = r.json()
    assert data["provider"] == "ollama"
    assert data["key_env_var"] is None


@pytest.mark.asyncio
async def test_detect_provider_custom(client):
    r = await client.post("/api/settings/detect-provider",
                          json={"base_url": "http://my-custom-server:7777"})
    assert r.status_code == 200
    data = r.json()
    assert data["provider"] == "custom"


@pytest.mark.asyncio
async def test_get_local_scan_returns_503_when_scanner_raises(client):
    """GET /api/settings/local-scan returns 503 when scan_all raises."""
    with patch("api.settings.LocalServerScanner") as MockScanner:
        instance = MockScanner.instance.return_value
        instance.scan_all = AsyncMock(side_effect=RuntimeError("scanner boom"))
        r = await client.get("/api/settings/local-scan")
    assert r.status_code == 503


@pytest.mark.asyncio
async def test_post_local_scan_refresh_returns_503_when_scanner_raises(client):
    """POST /api/settings/local-scan/refresh returns 503 when scan_all raises."""
    with patch("api.settings.LocalServerScanner") as MockScanner:
        instance = MockScanner.instance.return_value
        instance.scan_all = AsyncMock(side_effect=RuntimeError("refresh boom"))
        r = await client.post("/api/settings/local-scan/refresh")
    assert r.status_code == 503
