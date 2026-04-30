import pytest
import httpx
from unittest.mock import MagicMock

from core.web_search import _is_valid_url
import core.web_search as _ws


class _FakeClient:
    """Async context manager simulating httpx.AsyncClient for URL validation tests."""

    def __init__(self, status_code=None, exc=None):
        self._status_code = status_code
        self._exc = exc

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def head(self, url, **kwargs):
        if self._exc is not None:
            raise self._exc
        resp = MagicMock()
        resp.status_code = self._status_code
        return resp


@pytest.mark.asyncio
async def test_is_valid_url_accepts_200(monkeypatch):
    monkeypatch.setattr(_ws.httpx, "AsyncClient", lambda **kwargs: _FakeClient(status_code=200))
    assert await _is_valid_url("https://example.com") is True


@pytest.mark.asyncio
async def test_is_valid_url_rejects_404(monkeypatch):
    monkeypatch.setattr(_ws.httpx, "AsyncClient", lambda **kwargs: _FakeClient(status_code=404))
    assert await _is_valid_url("https://example.com/missing") is False


@pytest.mark.asyncio
async def test_is_valid_url_rejects_suspicious_pattern():
    assert await _is_valid_url("https://bit.ly/abc123") is False


@pytest.mark.asyncio
async def test_is_valid_url_handles_exception_gracefully(monkeypatch):
    monkeypatch.setattr(
        _ws.httpx, "AsyncClient",
        lambda **kwargs: _FakeClient(exc=httpx.ConnectError("Network error")),
    )
    assert await _is_valid_url("https://example.com") is False

