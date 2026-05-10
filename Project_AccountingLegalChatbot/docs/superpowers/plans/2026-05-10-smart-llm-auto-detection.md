# Smart LLM Auto-Detection Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Auto-detect running local inference servers (Ollama, LM Studio, TGI, Kobold.cpp) at startup and expose them in a "Local Models" UI group, while also auto-identifying cloud providers from a base URL.

**Architecture:** A new `LocalServerScanner` singleton probes known localhost ports in parallel at startup (max 1s each) and caches results for 60s. Three new API endpoints serve the scan results and provider detection. The frontend gains a "Local Models" collapsible section above the existing cloud providers list.

**Tech Stack:** Python asyncio + httpx (backend probing), FastAPI (endpoints), React + TypeScript (frontend), pytest + respx (tests).

---

## File Map

| Action  | Path | Purpose |
|---------|------|---------|
| Create  | `backend/core/local_scanner.py` | `LocalServer` dataclass + `LocalServerScanner` with `scan_all()`, `get_cached()` |
| Modify  | `backend/config.py` | Add `local_scan_ports`, `local_scan_timeout_s`, `local_scan_cache_ttl_s` |
| Modify  | `backend/core/llm_manager.py` | Add `LocalProvider` class + register in `_PROVIDER_MAP` |
| Modify  | `backend/api/settings.py` | Add 3 new endpoints: `GET /local-scan`, `POST /local-scan/refresh`, `POST /detect-provider` |
| Modify  | `backend/main.py` | Trigger background `scan_all()` at startup |
| Modify  | `frontend/src/pages/SettingsPage.tsx` | Add "Local Models" sidebar section + re-scan button + activate dropdown |
| Create  | `backend/tests/core/test_local_scanner.py` | Unit tests for scanner and URL detection |
| Create  | `backend/tests/api/test_settings_local_scan.py` | Integration tests for the 3 new endpoints |

---

## Task 1: Config — Add local-scan settings

**Files:**
- Modify: `backend/config.py:55-58` (after the Ollama block)

- [ ] **Step 1: Add 3 new fields to `Settings` class**

Open `backend/config.py`. After the Ollama block (lines ~55-57), add:

```python
    # ── Local Server Scanner ─────────────────────────────────────────
    local_scan_ports: list[int] = [11434, 1234, 8080, 5001]
    local_scan_timeout_s: float = 1.0
    local_scan_cache_ttl_s: int = 60
```

- [ ] **Step 2: Verify config loads without error**

```bash
cd ~/chatbot_local/Project_AccountingLegalChatbot/backend
~/chatbot_venv/bin/python3 -c "from config import settings; print(settings.local_scan_ports, settings.local_scan_timeout_s)"
```

Expected output:
```
[11434, 1234, 8080, 5001] 1.0
```

- [ ] **Step 3: Commit**

```bash
cd ~/chatbot_local
git add backend/config.py
git commit -m "feat: add local_scan config fields to Settings

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

## Task 2: LocalServerScanner — core detection module

**Files:**
- Create: `backend/core/local_scanner.py`

- [ ] **Step 1: Write failing test first**

Create `backend/tests/core/test_local_scanner.py`:

```python
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
    respx.get("http://localhost:11434/api/tags").mock(
        return_value=httpx.Response(200, json={"models": [{"name": "test-model"}]})
    )
    respx.get("http://localhost:1234/v1/models").mock(side_effect=httpx.ConnectError("refused"))
    respx.get("http://localhost:8080/health").mock(side_effect=httpx.ConnectError("refused"))
    respx.get("http://localhost:5001/api/v1/info").mock(side_effect=httpx.ConnectError("refused"))

    scanner = LocalServerScanner()
    scanner._cache = None
    first = await scanner.scan_all(timeout_s=2.0)

    # Network mock is exhausted after one call — second call must use cache
    second = await scanner.scan_all(timeout_s=2.0)
    assert first == second
```

- [ ] **Step 2: Run the test — confirm it fails with ImportError**

```bash
cd ~/chatbot_local/Project_AccountingLegalChatbot/backend
~/chatbot_venv/bin/python3 -m pytest tests/core/test_local_scanner.py -v 2>&1 | head -20
```

Expected: `ImportError: No module named 'core.local_scanner'`

- [ ] **Step 3: Implement `backend/core/local_scanner.py`**

Create the file with this exact content:

```python
"""
Local LLM Server Scanner.

Probes well-known localhost ports for running inference servers
(Ollama, LM Studio, HuggingFace TGI, Kobold.cpp) in parallel.
Results are cached for `local_scan_cache_ttl_s` seconds.
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Optional

import httpx

from config import settings

logger = logging.getLogger(__name__)

# ── Data model ─────────────────────────────────────────────────────

@dataclass
class LocalServer:
    provider: str       # "ollama" | "lmstudio" | "tgi" | "kobold"
    base_url: str
    online: bool
    models: list[str] = field(default_factory=list)
    latency_ms: int = 0


# ── URL-based provider identification ──────────────────────────────

_URL_PATTERNS: list[tuple[str, str, Optional[str], str]] = [
    # (substring_match, provider, key_env_var, key_label)
    ("anthropic.com",   "claude",   "ANTHROPIC_API_KEY", "Anthropic API Key"),
    ("openai.com",      "openai",   "OPENAI_API_KEY",    "OpenAI API Key"),
    ("nvidia.com",      "nvidia",   "NVIDIA_API_KEY",    "NVIDIA API Key"),
    ("nim",             "nvidia",   "NVIDIA_API_KEY",    "NVIDIA API Key"),
    ("mistral.ai",      "mistral",  "MISTRAL_API_KEY",   "Mistral API Key"),
    ("groq.com",        "groq",     "GROQ_API_KEY",      "Groq API Key"),
    ("localhost:11434", "ollama",   None,                ""),
    ("localhost:1234",  "lmstudio", None,                ""),
]


def detect_provider_from_url(base_url: str) -> dict:
    """
    Identify the LLM provider from a base URL.

    Returns:
        dict with keys: provider, key_env_var (None if not needed), key_label
    """
    url_lower = base_url.lower()
    for pattern, provider, key_env_var, key_label in _URL_PATTERNS:
        if pattern in url_lower:
            return {
                "provider": provider,
                "key_env_var": key_env_var,
                "key_label": key_label,
            }
    return {"provider": "custom", "key_env_var": None, "key_label": ""}


# ── Probe targets ──────────────────────────────────────────────────

@dataclass
class _ProbeTarget:
    provider: str
    port: int
    health_path: str
    models_path: str
    models_key: str   # JSON key in response that holds the list

_PROBE_TARGETS: list[_ProbeTarget] = [
    _ProbeTarget("ollama",   11434, "/api/tags",    "/api/tags",    "models"),
    _ProbeTarget("lmstudio", 1234,  "/v1/models",   "/v1/models",   "data"),
    _ProbeTarget("tgi",      8080,  "/health",      "/v1/models",   "data"),
    _ProbeTarget("kobold",   5001,  "/api/v1/info", "/api/v1/model","result"),
]


# ── Scanner ────────────────────────────────────────────────────────

class LocalServerScanner:
    """
    Singleton that probes local ports for LLM inference servers.

    Usage:
        scanner = LocalServerScanner.instance()
        servers = await scanner.scan_all()          # uses cache if fresh
        servers = await scanner.scan_all(force=True) # skip cache
    """

    _singleton: Optional["LocalServerScanner"] = None

    def __init__(self):
        self._cache: Optional[list[LocalServer]] = None
        self._cache_ts: float = 0.0

    @classmethod
    def instance(cls) -> "LocalServerScanner":
        if cls._singleton is None:
            cls._singleton = cls()
        return cls._singleton

    def get_cached(self) -> Optional[list[LocalServer]]:
        """Return cached results if still within TTL, else None."""
        ttl = settings.local_scan_cache_ttl_s
        if self._cache is not None and (time.monotonic() - self._cache_ts) < ttl:
            return self._cache
        return None

    async def scan_all(self, timeout_s: Optional[float] = None, force: bool = False) -> list[LocalServer]:
        """
        Probe all configured ports in parallel.

        Args:
            timeout_s: Per-probe HTTP timeout. Defaults to settings.local_scan_timeout_s.
            force: If True, bypass cache.
        """
        if not force:
            cached = self.get_cached()
            if cached is not None:
                return cached

        _timeout = timeout_s if timeout_s is not None else settings.local_scan_timeout_s
        tasks = [self._probe_one(t, _timeout) for t in _PROBE_TARGETS]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        servers: list[LocalServer] = []
        for t, result in zip(_PROBE_TARGETS, results):
            if isinstance(result, LocalServer):
                servers.append(result)
            else:
                servers.append(LocalServer(
                    provider=t.provider,
                    base_url=f"http://localhost:{t.port}",
                    online=False,
                ))

        self._cache = servers
        self._cache_ts = time.monotonic()
        online = [s for s in servers if s.online]
        logger.info("Local scan: %d/%d servers online: %s",
                    len(online), len(servers),
                    [s.provider for s in online])
        return servers

    async def _probe_one(self, target: _ProbeTarget, timeout_s: float) -> LocalServer:
        base = f"http://localhost:{target.port}"
        t0 = time.monotonic()
        try:
            async with httpx.AsyncClient(timeout=timeout_s) as client:
                resp = await client.get(f"{base}{target.health_path}")
                resp.raise_for_status()
                latency_ms = int((time.monotonic() - t0) * 1000)

                # Parse models from the health/models endpoint
                models: list[str] = []
                try:
                    data = resp.json()
                    raw = data.get(target.models_key, [])
                    if isinstance(raw, list):
                        for item in raw:
                            if isinstance(item, dict):
                                name = item.get("name") or item.get("id") or ""
                            else:
                                name = str(item)
                            if name:
                                models.append(name)
                except Exception:
                    pass

                # For TGI: health is /health, models is a separate endpoint
                if target.provider == "tgi" and not models:
                    try:
                        mr = await client.get(f"{base}{target.models_path}")
                        mdata = mr.json().get(target.models_key, [])
                        models = [m.get("id", "") for m in mdata if isinstance(m, dict)]
                    except Exception:
                        pass

                return LocalServer(
                    provider=target.provider,
                    base_url=base,
                    online=True,
                    models=models,
                    latency_ms=latency_ms,
                )
        except Exception:
            return LocalServer(
                provider=target.provider,
                base_url=base,
                online=False,
            )
```

- [ ] **Step 4: Run tests — all must pass**

```bash
cd ~/chatbot_local/Project_AccountingLegalChatbot/backend
~/chatbot_venv/bin/python3 -m pytest tests/core/test_local_scanner.py -v
```

Expected:
```
PASSED tests/core/test_local_scanner.py::test_detect_anthropic
PASSED tests/core/test_local_scanner.py::test_detect_openai
PASSED tests/core/test_local_scanner.py::test_detect_nvidia
PASSED tests/core/test_local_scanner.py::test_detect_mistral
PASSED tests/core/test_local_scanner.py::test_detect_groq
PASSED tests/core/test_local_scanner.py::test_detect_ollama_localhost
PASSED tests/core/test_local_scanner.py::test_detect_lmstudio_localhost
PASSED tests/core/test_local_scanner.py::test_detect_custom
PASSED tests/core/test_local_scanner.py::test_scan_all_ollama_online
PASSED tests/core/test_local_scanner.py::test_scan_all_all_offline
PASSED tests/core/test_local_scanner.py::test_scan_all_uses_cache
11 passed
```

- [ ] **Step 5: Commit**

```bash
cd ~/chatbot_local
git add backend/core/local_scanner.py backend/tests/core/test_local_scanner.py
git commit -m "feat: add LocalServerScanner with parallel port probing and URL detection

- Probes ports 11434, 1234, 8080, 5001 in parallel (1s timeout each)
- 60-second result cache to avoid repeated network calls
- detect_provider_from_url() maps base URLs to provider + env var hint
- 11 unit tests with respx HTTP mocking

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

## Task 3: LocalProvider — OpenAI-compat wrapper for LM Studio / TGI / Kobold

**Files:**
- Modify: `backend/core/llm_manager.py` — add class after `OllamaProvider` (line ~1192), register in `_PROVIDER_MAP`

- [ ] **Step 1: Add `LocalProvider` class after `OllamaProvider` (~line 1192 of llm_manager.py)**

Insert this block between the `OllamaProvider` class closing and the `# Factory` comment:

```python
# ═══════════════════════════════════════════════════════════════════
# LocalProvider (OpenAI-compatible: LM Studio, TGI, Kobold.cpp)
# ═══════════════════════════════════════════════════════════════════

class LocalProvider(BaseLLMProvider):
    """
    Generic OpenAI-compatible provider for any local inference server
    that speaks /v1/chat/completions (LM Studio, HuggingFace TGI, Kobold.cpp).

    Ollama's native /api/chat protocol is handled by OllamaProvider.
    """

    def __init__(self, base_url: str, model: str, api_key: str = "sk-local"):
        super().__init__(api_key=api_key, model=model, base_url=base_url)
        self.provider_name = "local"

    async def chat(self, messages, temperature=0.7, max_tokens=4096, reasoning_effort=None):
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False,
        }
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(connect=5.0, read=120.0, write=10.0, pool=5.0)
        ) as client:
            resp = await client.post(
                f"{self.base_url}/v1/chat/completions",
                json=payload,
                headers={"Authorization": f"Bearer {self.api_key}"},
            )
            resp.raise_for_status()
            data = resp.json()

        content = data["choices"][0]["message"]["content"]
        return LLMResponse(
            content=content,
            model=data.get("model", self.model),
            provider=self.provider_name,
            tokens_used=data.get("usage", {}).get("total_tokens", 0),
            finish_reason=data["choices"][0].get("finish_reason", "stop"),
        )

    async def chat_stream(self, messages, temperature=0.7, max_tokens=4096, reasoning_effort=None):
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
        }
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(connect=5.0, read=120.0, write=10.0, pool=5.0)
        ) as client:
            async with client.stream(
                "POST",
                f"{self.base_url}/v1/chat/completions",
                json=payload,
                headers={"Authorization": f"Bearer {self.api_key}"},
            ) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line or not line.startswith("data: "):
                        continue
                    data_str = line[6:]
                    if data_str.strip() == "[DONE]":
                        break
                    try:
                        chunk = json.loads(data_str)
                        content = chunk["choices"][0].get("delta", {}).get("content", "")
                        if content:
                            yield content
                    except (json.JSONDecodeError, KeyError, IndexError):
                        continue
```

- [ ] **Step 2: Register `LocalProvider` in `_PROVIDER_MAP` (after the "ollama" entry)**

In `llm_manager.py`, find the `_PROVIDER_MAP` dict and add `lmstudio` entry after `ollama`:

```python
    "lmstudio": lambda: LocalProvider(
        base_url="http://localhost:1234",
        model=getattr(settings, "lmstudio_model", "local-model"),
    ),
```

- [ ] **Step 3: Verify import works**

```bash
cd ~/chatbot_local/Project_AccountingLegalChatbot/backend
~/chatbot_venv/bin/python3 -c "from core.llm_manager import LocalProvider; print('LocalProvider OK')"
```

Expected: `LocalProvider OK`

- [ ] **Step 4: Commit**

```bash
cd ~/chatbot_local
git add backend/core/llm_manager.py
git commit -m "feat: add LocalProvider for OpenAI-compat local servers (LM Studio, TGI, Kobold)

- LocalProvider wraps any /v1/chat/completions endpoint
- Registered as 'lmstudio' in _PROVIDER_MAP
- Supports both chat() and chat_stream()

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

## Task 4: API Endpoints — /local-scan and /detect-provider

**Files:**
- Modify: `backend/api/settings.py` — append 3 new endpoint functions + 2 new Pydantic models
- Create: `backend/tests/api/test_settings_local_scan.py`

- [ ] **Step 1: Write failing integration tests**

Create `backend/tests/api/test_settings_local_scan.py`:

```python
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
        instance.get_cached.return_value = mock_servers
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
        instance.get_cached.return_value = None
        instance.scan_all = AsyncMock(return_value=mock_servers)
        r = await client.get("/api/settings/local-scan")

    assert r.status_code == 200
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
```

- [ ] **Step 2: Run tests — confirm they fail**

```bash
cd ~/chatbot_local/Project_AccountingLegalChatbot/backend
~/chatbot_venv/bin/python3 -m pytest tests/api/test_settings_local_scan.py -v 2>&1 | head -20
```

Expected: Multiple failures — endpoints don't exist yet.

- [ ] **Step 3: Add Pydantic models and 3 endpoints to `backend/api/settings.py`**

At the top of `settings.py`, add the import (in the existing imports block):

```python
from core.local_scanner import LocalServerScanner, detect_provider_from_url
```

Add these two Pydantic models in the `# ── Schemas ───` section:

```python
class LocalServerInfo(BaseModel):
    provider: str
    base_url: str
    online: bool
    models: list[str]
    latency_ms: int

class LocalScanResponse(BaseModel):
    scan_time: Optional[str] = None
    cache_age_s: int = 0
    servers: list[LocalServerInfo]

class DetectProviderRequest(BaseModel):
    base_url: str
    api_key: Optional[str] = None

class DetectProviderResponse(BaseModel):
    provider: str
    key_env_var: Optional[str]
    key_label: str
    key_valid: bool
```

Add these 3 endpoint functions at the end of `settings.py`:

```python
import time as _time


@router.get("/local-scan", response_model=LocalScanResponse)
async def get_local_scan():
    """
    Return cached local server scan results.
    If cache is empty, triggers a fresh scan first.
    Always returns 200 (servers may all be offline).
    """
    scanner = LocalServerScanner.instance()
    servers = scanner.get_cached()
    cache_age = 0
    if servers is None:
        servers = await scanner.scan_all()
    else:
        cache_age = int(_time.monotonic() - scanner._cache_ts)

    return LocalScanResponse(
        cache_age_s=cache_age,
        servers=[
            LocalServerInfo(
                provider=s.provider,
                base_url=s.base_url,
                online=s.online,
                models=s.models,
                latency_ms=s.latency_ms,
            )
            for s in servers
        ],
    )


@router.post("/local-scan/refresh", response_model=LocalScanResponse)
async def refresh_local_scan():
    """Trigger a fresh local port scan, bypassing the cache."""
    scanner = LocalServerScanner.instance()
    servers = await scanner.scan_all(force=True)
    return LocalScanResponse(
        cache_age_s=0,
        servers=[
            LocalServerInfo(
                provider=s.provider,
                base_url=s.base_url,
                online=s.online,
                models=s.models,
                latency_ms=s.latency_ms,
            )
            for s in servers
        ],
    )


@router.post("/detect-provider", response_model=DetectProviderResponse)
async def detect_provider(req: DetectProviderRequest):
    """
    Identify the LLM provider from a base URL.
    Optionally validates the API key with a lightweight test call.
    """
    info = detect_provider_from_url(req.base_url)
    key_valid = False

    # Try a lightweight validation if key and a cloud URL are provided
    if req.api_key and info["key_env_var"]:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                test_url = req.base_url.rstrip("/") + "/models"
                resp = await client.get(
                    test_url,
                    headers={"Authorization": f"Bearer {req.api_key}"},
                )
                key_valid = resp.status_code == 200
        except Exception:
            key_valid = False

    return DetectProviderResponse(
        provider=info["provider"],
        key_env_var=info.get("key_env_var"),
        key_label=info.get("key_label", ""),
        key_valid=key_valid,
    )
```

- [ ] **Step 4: Run integration tests — all must pass**

```bash
cd ~/chatbot_local/Project_AccountingLegalChatbot/backend
~/chatbot_venv/bin/python3 -m pytest tests/api/test_settings_local_scan.py -v
```

Expected: 7 tests, all PASSED.

- [ ] **Step 5: Smoke test the live endpoints**

```bash
curl -s http://localhost:8002/api/settings/local-scan | python3 -m json.tool | head -20
curl -s -X POST http://localhost:8002/api/settings/detect-provider \
     -H "Content-Type: application/json" \
     -d '{"base_url":"http://localhost:11434"}' | python3 -m json.tool
```

Expected for first:
```json
{ "cache_age_s": 0, "servers": [ { "provider": "ollama", "online": true, ... } ] }
```

Expected for second:
```json
{ "provider": "ollama", "key_env_var": null, "key_label": "", "key_valid": false }
```

- [ ] **Step 6: Commit**

```bash
cd ~/chatbot_local
git add backend/api/settings.py backend/tests/api/test_settings_local_scan.py
git commit -m "feat: add /local-scan and /detect-provider API endpoints

- GET /api/settings/local-scan returns cached scan (triggers scan if cache empty)
- POST /api/settings/local-scan/refresh forces fresh probe of all ports
- POST /api/settings/detect-provider maps URL pattern to provider + key hint
- Integration tests: 7 tests all passing

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

## Task 5: Startup — trigger background scan in main.py

**Files:**
- Modify: `backend/main.py` — add background scan task in `lifespan()`, after the existing startup source scan

- [ ] **Step 1: Add background scan to lifespan (after line ~156 in main.py)**

After `asyncio.create_task(_startup_source_scan())`, add:

```python
    # Kick off local inference server scan in the background (non-blocking)
    from core.local_scanner import LocalServerScanner
    asyncio.create_task(LocalServerScanner.instance().scan_all())
    logger.info("[OK] Local server scan started in background")
```

- [ ] **Step 2: Restart backend and verify scan log line appears**

```bash
# Kill existing backend
lsof -ti tcp:8002 | xargs kill 2>/dev/null || true
sleep 1
cd ~/chatbot_local/Project_AccountingLegalChatbot/backend
nohup ~/chatbot_venv/bin/python3 -m uvicorn main:app --host 0.0.0.0 --port 8002 \
      >> ~/chatbot_local/logs/backend.log 2>&1 &
sleep 6
grep "Local" ~/chatbot_local/logs/backend.log | tail -5
```

Expected log line:
```
[OK] Local server scan started in background
...
Local scan: 1/4 servers online: ['ollama']
```

- [ ] **Step 3: Verify endpoint returns Ollama online**

```bash
curl -s http://localhost:8002/api/settings/local-scan | python3 -m json.tool
```

Expected: Ollama online, other 3 offline.

- [ ] **Step 4: Commit**

```bash
cd ~/chatbot_local
git add backend/main.py
git commit -m "feat: trigger LocalServerScanner background scan at startup

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

## Task 6: Frontend — "Local Models" sidebar section

**Files:**
- Modify: `frontend/src/pages/SettingsPage.tsx`

- [ ] **Step 1: Add `LocalServerInfo` interface and `LocalScanResult` state**

At the top of `SettingsPage.tsx`, after the existing interfaces, add:

```typescript
interface LocalServerInfo {
  provider: string;
  base_url: string;
  online: boolean;
  models: string[];
  latency_ms: number;
}

interface LocalScanResult {
  cache_age_s: number;
  servers: LocalServerInfo[];
}
```

- [ ] **Step 2: Add state variables (after the existing `hasFastKey` state, ~line 59)**

```typescript
const [localScan,       setLocalScan]       = useState<LocalScanResult | null>(null);
const [scanning,        setScanning]        = useState(false);
const [expandedLocal,   setExpandedLocal]   = useState<string | null>(null);
const [activatingLocal, setActivatingLocal] = useState<string | null>(null);
```

- [ ] **Step 3: Add `fetchLocalScan` function (after the `fetchEmbeddingInfo` function)**

```typescript
const fetchLocalScan = () => {
  API.get('/api/settings/local-scan')
    .then(r => setLocalScan(r.data as LocalScanResult))
    .catch(() => {});
};

const refreshLocalScan = async () => {
  setScanning(true);
  try {
    const r = await API.post('/api/settings/local-scan/refresh');
    setLocalScan(r.data as LocalScanResult);
    flash('Local scan complete', true);
  } catch (e) {
    flash(getErrMsg(e, 'Scan failed'), false);
  } finally {
    setScanning(false);
  }
};

const activateLocalModel = async (provider: string, model: string) => {
  setActivatingLocal(`${provider}:${model}`);
  try {
    await API.put('/api/settings/provider', { provider, model, activate: true });
    const r = await API.get('/api/settings/current');
    setFullSettings(r.data);
    flash(`Activated ${provider} — ${model}`, true);
  } catch (e) {
    flash(getErrMsg(e, 'Activation failed'), false);
  } finally {
    setActivatingLocal(null);
  }
};
```

- [ ] **Step 4: Call `fetchLocalScan()` inside the existing `useEffect`**

In the `useEffect` block (around line 97), add `fetchLocalScan();` right after `fetchEmbeddingInfo();`:

```typescript
  useEffect(() => {
    API.get('/api/settings/current')
      .then(r => { /* ... existing code ... */ })
      .catch(...)
      .finally(...);
    fetchEmbeddingInfo();
    fetchLocalScan();   // ← ADD THIS LINE
  }, []);
```

- [ ] **Step 5: Add the "Local Models" section in the JSX sidebar (inside `.provider-card-list`, before the existing provider cards map)**

Find the line with `<div className="provider-card-list">` and add this block at the beginning of that div (before the `<div className="settings-section-title"...>Providers</div>` line):

```tsx
              {/* ── Local Models ──────────────────────────────────── */}
              <div className="settings-section-title" style={{ marginBottom: '8px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span>Local Models</span>
                <button
                  className="btn btn-secondary"
                  style={{ padding: '2px 8px', fontSize: '0.7rem' }}
                  onClick={refreshLocalScan}
                  disabled={scanning}
                  title="Re-scan local ports"
                >
                  {scanning ? '…' : '↺'}
                </button>
              </div>

              {localScan ? localScan.servers.map(server => (
                <div key={server.provider} style={{ marginBottom: '6px', borderRadius: '8px', background: 'var(--surface-2)', padding: '8px 10px' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px', cursor: server.online ? 'pointer' : 'default' }}
                    onClick={() => server.online && setExpandedLocal(expandedLocal === server.provider ? null : server.provider)}>
                    <span style={{ fontSize: '10px', color: server.online ? 'var(--green)' : 'var(--text-3)' }}>
                      {server.online ? '●' : '○'}
                    </span>
                    <span style={{ fontSize: '0.82rem', fontWeight: 600 }}>
                      {server.provider === 'ollama' ? 'Ollama' :
                       server.provider === 'lmstudio' ? 'LM Studio' :
                       server.provider === 'tgi' ? 'HuggingFace TGI' :
                       server.provider === 'kobold' ? 'Kobold.cpp' : server.provider}
                    </span>
                    {server.online && (
                      <span style={{ fontSize: '0.7rem', color: 'var(--text-2)' }}>
                        {server.models.length} model{server.models.length !== 1 ? 's' : ''}
                      </span>
                    )}
                    {!server.online && (
                      <span style={{ fontSize: '0.7rem', color: 'var(--text-3)' }}>(offline)</span>
                    )}
                  </div>

                  {server.online && expandedLocal === server.provider && (
                    <div style={{ marginTop: '6px', paddingLeft: '18px' }}>
                      {server.models.map(model => (
                        <div key={model} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '2px 0' }}>
                          <span style={{ fontSize: '0.72rem', color: 'var(--text-2)', fontFamily: 'monospace' }}>
                            {model}
                          </span>
                          <button
                            className="btn btn-primary"
                            style={{ padding: '1px 8px', fontSize: '0.68rem' }}
                            onClick={() => activateLocalModel(server.provider, model)}
                            disabled={activatingLocal === `${server.provider}:${model}`}
                          >
                            {activatingLocal === `${server.provider}:${model}` ? '…' : 'Activate'}
                          </button>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )) : (
                <div style={{ fontSize: '0.75rem', color: 'var(--text-3)', padding: '4px 0 8px' }}>
                  Scanning local ports…
                </div>
              )}
```

- [ ] **Step 6: Build frontend to confirm no TypeScript errors**

```bash
cd ~/chatbot_local/Project_AccountingLegalChatbot/frontend
npm run build 2>&1 | tail -20
```

Expected: build completes with no errors.

- [ ] **Step 7: Start frontend and verify "Local Models" section renders**

```bash
cd ~/chatbot_local/Project_AccountingLegalChatbot/frontend
npm run dev &
sleep 4
echo "Open http://localhost:5173 → API Settings → check 'Local Models' section"
```

Manual check: Ollama shows `●` (online) with `qwen3.5:35b-a3b-coding-nvfp4` listed. LM Studio, TGI, Kobold show `○` (offline). Refresh button `↺` works.

- [ ] **Step 8: Commit**

```bash
cd ~/chatbot_local
git add frontend/src/pages/SettingsPage.tsx
git commit -m "feat: add 'Local Models' sidebar section to SettingsPage

- Shows online/offline status for Ollama, LM Studio, TGI, Kobold
- Re-scan button triggers POST /api/settings/local-scan/refresh
- Expandable model list with per-model [Activate] button
- Calls /api/settings/local-scan on page load

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

## Task 7: Frontend — URL auto-detect in "Add Provider" form

**Files:**
- Modify: `frontend/src/pages/SettingsPage.tsx` — enhance the Base URL input to call `/detect-provider` on blur

- [ ] **Step 1: Add `detectedProvider` state (after `activatingLocal` state)**

```typescript
const [detectedProvider, setDetectedProvider] = useState<{ provider: string; key_env_var: string | null; key_label: string } | null>(null);
```

- [ ] **Step 2: Add `handleBaseUrlBlur` function (after `activateLocalModel`)**

```typescript
const handleBaseUrlBlur = async (url: string) => {
  if (!url || !url.startsWith('http')) {
    setDetectedProvider(null);
    return;
  }
  try {
    const r = await API.post('/api/settings/detect-provider', { base_url: url });
    const d = r.data as { provider: string; key_env_var: string | null; key_label: string };
    if (d.provider !== 'custom') {
      setDetectedProvider(d);
    } else {
      setDetectedProvider(null);
    }
  } catch {
    setDetectedProvider(null);
  }
};
```

- [ ] **Step 3: Wire `onBlur` to the existing Base URL input and show the detected provider hint**

Find the existing Base URL `<input>` in `SettingsPage.tsx` (around line 291-298):

```tsx
              {meta.hasBaseUrl && (
                <div className="settings-field">
                  <label className="settings-label">Base URL</label>
                  <input
                    type="text"
                    className="settings-input"
                    placeholder="https://..."
                    value={editBaseUrl}
                    onChange={e => setEditBaseUrl(e.target.value)}
                  />
                </div>
              )}
```

Replace with:

```tsx
              {meta.hasBaseUrl && (
                <div className="settings-field">
                  <label className="settings-label">Base URL</label>
                  <input
                    type="text"
                    className="settings-input"
                    placeholder="https://..."
                    value={editBaseUrl}
                    onChange={e => { setEditBaseUrl(e.target.value); setDetectedProvider(null); }}
                    onBlur={e => handleBaseUrlBlur(e.target.value)}
                  />
                  {detectedProvider && (
                    <div style={{ fontSize: '0.72rem', color: 'var(--primary)', marginTop: '4px' }}>
                      ✓ Detected: <strong>{detectedProvider.provider}</strong>
                      {detectedProvider.key_label && ` — key field: ${detectedProvider.key_label}`}
                    </div>
                  )}
                </div>
              )}
```

- [ ] **Step 4: Build and verify no TypeScript errors**

```bash
cd ~/chatbot_local/Project_AccountingLegalChatbot/frontend
npm run build 2>&1 | tail -10
```

Expected: clean build.

- [ ] **Step 5: Manual test**
  - Open Settings → select NVIDIA → change Base URL to `https://api.openai.com/v1` → click away (blur)
  - Expect `✓ Detected: openai — key field: OpenAI API Key` hint appears below the URL field.

- [ ] **Step 6: Commit**

```bash
cd ~/chatbot_local
git add frontend/src/pages/SettingsPage.tsx
git commit -m "feat: auto-detect provider from Base URL on blur in Settings form

- Calls POST /api/settings/detect-provider on URL field blur
- Shows 'Detected: openai — key field: OpenAI API Key' hint inline
- Clears hint when URL is changed

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

## Task 8: Run full test suite + E2E verification

**Files:** All test files (read-only in this task)

- [ ] **Step 1: Run complete backend test suite**

```bash
cd ~/chatbot_local/Project_AccountingLegalChatbot/backend
~/chatbot_venv/bin/python3 -m pytest tests/ -v --tb=short 2>&1 | tail -40
```

Expected: All tests pass. Any pre-existing failures should be the same as before this feature (do not introduce new failures).

- [ ] **Step 2: Verify scan endpoint live with Ollama**

```bash
curl -s http://localhost:8002/api/settings/local-scan | python3 -m json.tool
```

Expected: `ollama` server shows `"online": true` with `qwen3.5:35b-a3b-coding-nvfp4` in models list.

- [ ] **Step 3: Test refresh endpoint**

```bash
curl -s -X POST http://localhost:8002/api/settings/local-scan/refresh | python3 -m json.tool | grep -A3 '"ollama"'
```

Expected: Fresh scan result with Ollama online.

- [ ] **Step 4: Test Ollama chat end-to-end**

```bash
# Create a conversation and send a message via Ollama
CONV=$(curl -s -X POST http://localhost:8002/api/conversations \
       -H "Content-Type: application/json" \
       -d '{"title":"Ollama test"}' | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")

curl -s -X POST http://localhost:8002/api/chat/send \
     -H "Content-Type: application/json" \
     -d "{\"conversation_id\":\"$CONV\",\"message\":\"Reply with exactly: OLLAMA_OK\",\"mode\":\"fast\",\"stream\":false}" \
     | python3 -c "import sys,json; d=json.load(sys.stdin); print('Reply:', d.get('content','')[:80])"
```

Expected: Reply contains `OLLAMA_OK` (or a reasonable Ollama response).

- [ ] **Step 5: Final commit and push**

```bash
cd ~/chatbot_local
git push origin main
```

---

## Summary

| Task | Component | Tests |
|------|-----------|-------|
| 1 | `config.py` — 3 new settings fields | `python -c "from config import settings"` |
| 2 | `core/local_scanner.py` — scanner + URL detect | 11 unit tests |
| 3 | `core/llm_manager.py` — `LocalProvider` class | Import smoke test |
| 4 | `api/settings.py` — 3 new endpoints | 7 integration tests |
| 5 | `main.py` — startup background scan | Log line verification |
| 6 | `SettingsPage.tsx` — Local Models UI | Build + manual |
| 7 | `SettingsPage.tsx` — URL auto-detect | Build + manual blur test |
| 8 | Full suite + E2E | All tests + live curl checks |
