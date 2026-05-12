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
    ("mistral.ai",      "mistral",  "MISTRAL_API_KEY",   "Mistral API Key"),
    ("groq.com",        "groq",     "GROQ_API_KEY",      "Groq API Key"),
    ("opencode.ai",    "opencode",  "OPENCODE_API_KEY",  "OpenCode API Key (optional)"),
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
    separate_models_fetch: bool = False

_PROBE_TARGETS: list[_ProbeTarget] = [
    _ProbeTarget("ollama",   11434, "/api/tags",    "/api/tags",    "models"),
    _ProbeTarget("lmstudio", 1234,  "/v1/models",   "/v1/models",   "data"),
    _ProbeTarget("tgi",      8080,  "/health",      "/v1/models",   "data",  True),
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

    def get_cache_age_s(self) -> int:
        """Return seconds since last successful scan, or 0 if no cache exists."""
        if self._cache_ts == 0.0:
            return 0
        return int(time.monotonic() - self._cache_ts)

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
        active_targets = [t for t in _PROBE_TARGETS if t.port in settings.local_scan_ports]
        tasks = [self._probe_one(t, _timeout) for t in active_targets]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        servers: list[LocalServer] = []
        for t, result in zip(active_targets, results):
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

                # For targets that use a separate models endpoint (e.g. TGI)
                if target.separate_models_fetch and not models:
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
