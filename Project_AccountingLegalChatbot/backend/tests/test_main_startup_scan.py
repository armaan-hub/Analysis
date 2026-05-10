"""Test that LocalServerScanner.scan_all() is called during app lifespan startup."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

pytestmark = pytest.mark.asyncio


async def test_startup_triggers_local_scan(monkeypatch):
    """LocalServerScanner.scan_all() must be awaited during app startup."""
    monkeypatch.setenv("TESTING", "1")
    monkeypatch.setenv("LLM_PROVIDER", "nvidia")

    with patch("main.LocalServerScanner") as mock_cls:
        mock_instance = MagicMock()
        mock_instance.scan_all = AsyncMock(return_value=[])
        mock_cls.instance.return_value = mock_instance

        from main import app

        async with app.router.lifespan_context(app):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                r = await client.get("/health")

    mock_instance.scan_all.assert_called_once()
    assert r.status_code == 200
