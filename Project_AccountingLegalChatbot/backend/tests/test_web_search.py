import pytest
import httpx

from core.web_search import _is_valid_url
import core.web_search as _ws


class _FakeClient:
    """Async context manager simulating httpx.AsyncClient for URL validation tests."""

    def __init__(self, status=200, exc=None):
        self.status = status
        self.exc = exc

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def head(self, *a, **kw):
        if self.exc is not None:
            raise self.exc
        return type("R", (), {"status_code": self.status})()


@pytest.mark.asyncio
async def test_is_valid_url_accepts_200(monkeypatch):
    monkeypatch.setattr(_ws.httpx, "AsyncClient", lambda **kwargs: _FakeClient(status=200))
    assert await _is_valid_url("https://example.com") is True


@pytest.mark.asyncio
async def test_is_valid_url_rejects_404(monkeypatch):
    monkeypatch.setattr(_ws.httpx, "AsyncClient", lambda **kwargs: _FakeClient(status=404))
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


@pytest.mark.asyncio
async def test_is_valid_url_rejects_non_http_scheme(monkeypatch):
    """Non-HTTP/HTTPS schemes should be rejected without making a network call."""
    assert await _is_valid_url("ftp://example.com") is False


@pytest.mark.asyncio
async def test_is_valid_url_rejects_empty_string(monkeypatch):
    """Empty string should be rejected immediately."""
    assert await _is_valid_url("") is False


@pytest.mark.asyncio
async def test_is_valid_url_accepts_redirect(monkeypatch):
    """3xx redirects (status 301) should be accepted."""
    monkeypatch.setattr(
        _ws.httpx, "AsyncClient",
        lambda **kwargs: _FakeClient(status=301),
    )
    assert await _is_valid_url("https://example.com") is True


@pytest.mark.asyncio
async def test_is_valid_url_rejects_server_error(monkeypatch):
    """5xx server errors should be rejected."""
    monkeypatch.setattr(
        _ws.httpx, "AsyncClient",
        lambda **kwargs: _FakeClient(status=500),
    )
    assert await _is_valid_url("https://example.com") is False


@pytest.mark.asyncio
async def test_is_valid_url_handles_timeout(monkeypatch):
    """TimeoutException (subclass of HTTPError) should be caught and return False."""
    monkeypatch.setattr(
        _ws.httpx, "AsyncClient",
        lambda **kwargs: _FakeClient(exc=_ws.httpx.TimeoutException("timed out")),
    )
    assert await _is_valid_url("https://example.com") is False


def test_suspicious_patterns_block_twitter_with_path():
    """Twitter URLs with paths (real DDG results) should be blocked."""
    import re
    twitter_url = "https://twitter.com/user/status/123456"
    for pattern in _ws._SUSPICIOUS_URL_PATTERNS:
        if re.search(pattern, twitter_url, re.IGNORECASE):
            return
    pytest.fail("Twitter URL with path was not blocked by any pattern")


def test_suspicious_patterns_allow_huggingface_ml():
    """HuggingFace .ml file paths should NOT be blocked (TLD fix)."""
    import re
    hf_url = "https://huggingface.co/model/weights.ml"
    for pattern in _ws._SUSPICIOUS_URL_PATTERNS:
        if re.search(pattern, hf_url, re.IGNORECASE):
            pytest.fail(f"HuggingFace .ml URL was incorrectly blocked by pattern: {pattern!r}")


def test_suspicious_patterns_block_x_com():
    """x.com (Twitter rebrand) URLs should be blocked."""
    import re
    x_url = "https://x.com/user/status/123456"
    for pattern in _ws._SUSPICIOUS_URL_PATTERNS:
        if re.search(pattern, x_url, re.IGNORECASE):
            return
    pytest.fail("x.com URL was not blocked by any pattern")


def test_suspicious_patterns_allow_uae_error_path():
    """UAE gov URLs with 'error' in path should NOT be blocked (removed 404/error pattern)."""
    import re
    gov_url = "https://tax.gov.ae/en/Pages/Error/page-not-found.aspx"
    for pattern in _ws._SUSPICIOUS_URL_PATTERNS:
        if re.search(pattern, gov_url, re.IGNORECASE):
            pytest.fail(f"UAE gov error-path URL was incorrectly blocked by pattern: {pattern!r}")


def test_suspicious_patterns_allow_medium_in_path():
    """URLs with 'medium' in path (not medium.com) should NOT be blocked."""
    import re
    legal_url = "https://tax.gov.ae/mediumterm-plan.pdf"
    for pattern in _ws._SUSPICIOUS_URL_PATTERNS:
        if re.search(pattern, legal_url, re.IGNORECASE):
            pytest.fail(f"Legitimate URL with 'medium' in path was incorrectly blocked: {pattern!r}")


