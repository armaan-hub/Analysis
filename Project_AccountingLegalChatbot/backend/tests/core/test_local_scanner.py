"""Unit tests for LocalServerScanner."""
import asyncio
import pytest
import httpx
import respx
from unittest.mock import patch
from core.local_scanner import LocalServer, LocalServerScanner, detect_provider_from_url


# ── detect_provider_from_url ─────────────────────────────────────

def test_detect_anthropic():
    r = detect_provider_from_url("https://api.anthropic.com/v1")
    assert r["provider"] == "claude"
    assert r["key_env_var"] == "ANTHROPIC_API_KEY"


def test_detect_openai():
    r = detect_provider_from_url("https://api.openai.com/v1")
    assert r["provider"] == "openai"
    assert r["key_env_var"] == "OPENAI_API_KEY"


def test_detect_nvidia():
    r = detect_provider_from_url("https://integrate.api.nvidia.com/v1")
    assert r["provider"] == "nvidia"
    assert r["key_env_var"] == "NVIDIA_API_KEY"


def test_detect_mistral():
    r = detect_provider_from_url("https://api.mistral.ai/v1")
    assert r["provider"] == "mistral"
    assert r["key_env_var"] == "MISTRAL_API_KEY"


def test_detect_groq():
    r = detect_provider_from_url("https://api.groq.com/openai/v1")
    assert r["provider"] == "groq"
    assert r["key_env_var"] == "GROQ_API_KEY"


def test_detect_ollama_localhost():
    r = detect_provider_from_url("http://localhost:11434")
    assert r["provider"] == "ollama"
    assert r["key_env_var"] is None


def test_detect_lmstudio_localhost():
    r = detect_provider_from_url("http://localhost:1234")
    assert r["provider"] == "lmstudio"
    assert r["key_env_var"] is None


def test_detect_custom():
    r = detect_provider_from_url("http://localhost:9999")
    assert r["provider"] == "custom"
    assert r["key_env_var"] is None


# ── LocalServerScanner.scan_all ──────────────────────────────────

@pytest.mark.asyncio
@respx.mock
async def test_scan_all_ollama_online():
    """When Ollama responds, it should be marked online with its models."""
    respx.get("http://localhost:11434/api/tags").mock(
        return_value=httpx.Response(200, json={
            "models": [
                {"name": "qwen3.5:35b-a3b-coding-nvfp4"},
                {"name": "nomic-embed-text:latest"},
            ]
        })
    )
    # Other ports offline
    respx.get("http://localhost:1234/v1/models").mock(side_effect=httpx.ConnectError("refused"))
    respx.get("http://localhost:8080/health").mock(side_effect=httpx.ConnectError("refused"))
    respx.get("http://localhost:5001/api/v1/info").mock(side_effect=httpx.ConnectError("refused"))

    scanner = LocalServerScanner()
    scanner._cache = None  # force fresh scan
    servers = await scanner.scan_all(timeout_s=2.0)

    ollama = next(s for s in servers if s.provider == "ollama")
    assert ollama.online is True
    assert "qwen3.5:35b-a3b-coding-nvfp4" in ollama.models
    assert ollama.latency_ms >= 0

    lmstudio = next(s for s in servers if s.provider == "lmstudio")
    assert lmstudio.online is False
    assert lmstudio.models == []


@pytest.mark.asyncio
@respx.mock
async def test_scan_all_all_offline():
    """All ports offline → all servers marked offline, no exception raised."""
    for url in [
        "http://localhost:11434/api/tags",
        "http://localhost:1234/v1/models",
        "http://localhost:8080/health",
        "http://localhost:5001/api/v1/info",
    ]:
        respx.get(url).mock(side_effect=httpx.ConnectError("refused"))

    scanner = LocalServerScanner()
    scanner._cache = None
    servers = await scanner.scan_all(timeout_s=2.0)

    assert len(servers) == 4
    assert all(not s.online for s in servers)


@pytest.mark.asyncio
@respx.mock
async def test_scan_all_uses_cache():
    """Second call within TTL returns cache without hitting network."""
    ollama_route = respx.get("http://localhost:11434/api/tags").mock(
        return_value=httpx.Response(200, json={"models": [{"name": "test-model"}]})
    )
    respx.get("http://localhost:1234/v1/models").mock(side_effect=httpx.ConnectError("refused"))
    respx.get("http://localhost:8080/health").mock(side_effect=httpx.ConnectError("refused"))
    respx.get("http://localhost:5001/api/v1/info").mock(side_effect=httpx.ConnectError("refused"))

    scanner = LocalServerScanner()
    scanner._cache = None
    scanner._cache_ts = 0.0
    first = await scanner.scan_all(timeout_s=2.0)
    call_count_after_first = ollama_route.call_count

    # Second call — cache is fresh, must NOT hit network again
    second = await scanner.scan_all(timeout_s=2.0)
    assert ollama_route.call_count == call_count_after_first  # no new HTTP calls
    assert first == second
