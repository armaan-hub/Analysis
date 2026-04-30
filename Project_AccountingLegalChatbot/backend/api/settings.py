"""
Settings API – Manage LLM providers and application settings.
"""

import asyncio
import re
from pathlib import Path
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import httpx

from db.database import get_db
from db.models import UserSettings
from core.llm_manager import get_llm_provider, list_available_providers
from config import settings

router = APIRouter(prefix="/api/settings", tags=["Settings"])

_settings_lock = asyncio.Lock()

# Path to root .env (one level up from backend/)
_ENV_PATH = Path(__file__).resolve().parent.parent.parent / ".env"


# ── Schemas ───────────────────────────────────────────────────────

class ProviderInfo(BaseModel):
    name: str
    configured: bool
    is_active: bool

class ProviderSwitchRequest(BaseModel):
    provider: str

class ProviderUpdateRequest(BaseModel):
    provider: str
    api_key: Optional[str] = None
    model: Optional[str] = None
    base_url: Optional[str] = None
    fast_api_key: Optional[str] = None
    fast_model: Optional[str] = None
    activate: bool = False

class SettingUpdate(BaseModel):
    key: str
    value: str

class TestProviderResponse(BaseModel):
    success: bool
    provider: str
    model: str
    message: str

class ModelInfo(BaseModel):
    id: str
    name: str


# ── Helpers ───────────────────────────────────────────────────────

def _escape_env_value(value: str) -> str:
    """Escape a value for safe writing to .env file."""
    value = value.strip().replace('\n', '').replace('\r', '')
    if any(c in value for c in (' ', '#', '"', "'", '\\', '=')):
        value = '"' + value.replace('\\', '\\\\').replace('"', '\\"') + '"'
    return value


def _update_env_key(key: str, value: str) -> None:
    """Write or update a single key in the root .env file."""
    if not _ENV_PATH.exists():
        return
    text = _ENV_PATH.read_text(encoding="utf-8")
    pattern = re.compile(rf"^{re.escape(key)}\s*=.*$", re.MULTILINE)
    new_line = f"{key}={_escape_env_value(value)}"
    if pattern.search(text):
        text = pattern.sub(new_line, text)
    else:
        text = text.rstrip("\n") + f"\n{new_line}\n"
    _ENV_PATH.write_text(text, encoding="utf-8")


# ── Endpoints ─────────────────────────────────────────────────────

@router.get("/providers", response_model=list[ProviderInfo])
async def get_providers():
    """List all available LLM providers and their configuration status."""
    return list_available_providers()


@router.post("/providers/switch")
async def switch_provider(req: ProviderSwitchRequest):
    """Switch the active LLM provider."""
    available = [p["name"] for p in list_available_providers()]
    if req.provider not in available:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown provider '{req.provider}'. Available: {available}",
        )

    async with _settings_lock:
        _update_env_key("LLM_PROVIDER", req.provider)
        settings.llm_provider = req.provider
    return {
        "status": "switched",
        "active_provider": req.provider,
        "model": settings.active_model,
    }


@router.put("/provider")
async def update_provider(req: ProviderUpdateRequest):
    """
    Update API key, model, and/or base URL for a provider at runtime.
    Persists changes to .env so they survive restarts.
    Pass activate=true to also switch the active provider.
    """
    provider = req.provider.lower()
    # Tuple: (key_attr, key_env, model_attr, model_env, url_attr, url_env, fast_key_attr, fast_key_env, fast_model_attr, fast_model_env)
    _KEY_MAP = {
        "nvidia":  ("nvidia_api_key",   "NVIDIA_API_KEY",   "nvidia_model",   "NVIDIA_MODEL",   "nvidia_base_url", "NVIDIA_BASE_URL", "nvidia_fast_api_key", "NVIDIA_FAST_API_KEY", "nvidia_fast_model",   "NVIDIA_FAST_MODEL"),
        "openai":  ("openai_api_key",   "OPENAI_API_KEY",   "openai_model",   "OPENAI_MODEL",   None, None, None, None, None, None),
        "claude":  ("anthropic_api_key","ANTHROPIC_API_KEY","anthropic_model","ANTHROPIC_MODEL", None, None, None, None, None, None),
        "mistral": ("mistral_api_key",  "MISTRAL_API_KEY",  "mistral_model",  "MISTRAL_MODEL",  None, None, None, None, None, None),
        "groq":    ("groq_api_key",     "GROQ_API_KEY",     "groq_model",     "GROQ_MODEL",     None, None, None, None, "groq_fast_model", "GROQ_FAST_MODEL"),
        "ollama":  (None, None,          "ollama_model",    "OLLAMA_MODEL",   "ollama_base_url","OLLAMA_BASE_URL", None, None, None, None),
    }
    if provider not in _KEY_MAP:
        raise HTTPException(status_code=400, detail=f"Unknown provider '{provider}'")

    key_attr, key_env, model_attr, model_env, url_attr, url_env, fast_key_attr, fast_key_env, fast_model_attr, fast_model_env = _KEY_MAP[provider]

    async with _settings_lock:
        if req.api_key is not None and key_attr:
            _update_env_key(key_env, req.api_key)
            setattr(settings, key_attr, req.api_key)
        if req.model is not None and model_attr:
            _update_env_key(model_env, req.model)
            setattr(settings, model_attr, req.model)
        if req.base_url is not None and url_attr:
            _update_env_key(url_env, req.base_url)
            setattr(settings, url_attr, req.base_url)
        if req.fast_api_key is not None and fast_key_attr:
            _update_env_key(fast_key_env, req.fast_api_key)
            setattr(settings, fast_key_attr, req.fast_api_key)
        if req.fast_model is not None and fast_model_attr:
            _update_env_key(fast_model_env, req.fast_model)
            setattr(settings, fast_model_attr, req.fast_model)
        if req.activate:
            _update_env_key("LLM_PROVIDER", provider)
            settings.llm_provider = provider

    return {
        "status": "updated",
        "provider": provider,
        "active_provider": settings.llm_provider,
        "model": settings.active_model,
    }


def _parse_json_response(resp: httpx.Response, provider: str) -> dict:
    """Parse JSON from a provider response with a clear error on non-JSON body."""
    ct = resp.headers.get("content-type", "")
    if "application/json" not in ct and "text/json" not in ct:
        raise HTTPException(
            status_code=502,
            detail=f"{provider} API returned non-JSON ({ct}). "
                   f"Check that the Base URL is correct and the API key is valid.",
        )
    try:
        return resp.json()
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"{provider} API returned invalid JSON: {exc}",
        )


@router.get("/providers/{provider}/models", response_model=List[ModelInfo])
async def fetch_provider_models(provider: str):
    """
    Fetch available models from the provider's live API.
    Uses the API key currently configured for that provider.
    """
    provider = provider.lower()

    try:
        # ── NVIDIA NIM ────────────────────────────────────────────────
        if provider == "nvidia":
            if not settings.nvidia_api_key:
                raise HTTPException(status_code=400, detail="NVIDIA API key not configured")
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(
                    f"{settings.nvidia_base_url}/models",
                    headers={"Authorization": f"Bearer {settings.nvidia_api_key}"},
                )
                resp.raise_for_status()
                data = _parse_json_response(resp, "NVIDIA")
            models = sorted({m["id"] for m in data.get("data", [])})
            return [ModelInfo(id=m, name=m) for m in models]

        # ── OpenAI ────────────────────────────────────────────────────
        elif provider == "openai":
            if not settings.openai_api_key:
                raise HTTPException(status_code=400, detail="OpenAI API key not configured")
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(
                    "https://api.openai.com/v1/models",
                    headers={"Authorization": f"Bearer {settings.openai_api_key}"},
                )
                resp.raise_for_status()
                data = _parse_json_response(resp, "OpenAI")
            chat_models = sorted(
                m["id"] for m in data.get("data", [])
                if any(x in m["id"] for x in ("gpt-4", "gpt-3.5", "o1", "o3", "o4"))
            )
            return [ModelInfo(id=m, name=m) for m in chat_models]

        # ── Anthropic Claude ──────────────────────────────────────────
        elif provider == "claude":
            known = [
                "claude-opus-4-6",
                "claude-sonnet-4-6",
                "claude-haiku-4-5-20251001",
                "claude-3-5-sonnet-20241022",
                "claude-3-5-haiku-20241022",
                "claude-3-opus-20240229",
            ]
            return [ModelInfo(id=m, name=m) for m in known]

        # ── Mistral ───────────────────────────────────────────────────
        elif provider == "mistral":
            if not settings.mistral_api_key:
                raise HTTPException(status_code=400, detail="Mistral API key not configured")
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(
                    "https://api.mistral.ai/v1/models",
                    headers={"Authorization": f"Bearer {settings.mistral_api_key}"},
                )
                resp.raise_for_status()
                data = _parse_json_response(resp, "Mistral")
            models = sorted(m["id"] for m in data.get("data", []))
            return [ModelInfo(id=m, name=m) for m in models]

        # ── Ollama (local) ────────────────────────────────────────────
        elif provider == "ollama":
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    resp = await client.get(f"{settings.ollama_base_url}/api/tags")
                    resp.raise_for_status()
                    data = resp.json()
                models = sorted(m["name"] for m in data.get("models", []))
                return [ModelInfo(id=m, name=m) for m in models]
            except httpx.ConnectError:
                raise HTTPException(status_code=503, detail="Ollama is not running at the configured Base URL")

        # ── Groq ──────────────────────────────────────────────────────
        elif provider == "groq":
            if not settings.groq_api_key:
                raise HTTPException(status_code=400, detail="Groq API key not configured")
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(
                    f"{settings.groq_base_url}/models",
                    headers={"Authorization": f"Bearer {settings.groq_api_key}"},
                )
                resp.raise_for_status()
                data = _parse_json_response(resp, "Groq")
            models = sorted(m["id"] for m in data.get("data", []))
            return [ModelInfo(id=m, name=m) for m in models]

        else:
            raise HTTPException(status_code=400, detail=f"Unknown provider '{provider}'")

    except HTTPException:
        raise  # re-raise structured errors as-is
    except httpx.HTTPStatusError as exc:
        raise HTTPException(
            status_code=exc.response.status_code,
            detail=f"{provider} API error {exc.response.status_code}: {exc.response.text[:300]}",
        )
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail=f"Timeout contacting {provider} API")
    except httpx.ConnectError:
        raise HTTPException(status_code=503, detail=f"Cannot connect to {provider} API — check Base URL")


@router.post("/providers/test", response_model=TestProviderResponse)
async def test_provider(req: ProviderSwitchRequest):
    """Test a provider by sending a simple message."""
    try:
        llm = get_llm_provider(req.provider)
        response = await llm.chat(
            messages=[
                {"role": "user", "content": "Respond with exactly: 'Provider test successful.'"}
            ],
            max_tokens=50,
            temperature=0.0,
        )
        return TestProviderResponse(
            success=True,
            provider=response.provider,
            model=response.model,
            message=response.content[:200],
        )
    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail=f"Provider test failed: {str(e)}",
        )


@router.get("/current")
async def get_current_settings():
    """Get current application settings including per-provider config."""
    return {
        "llm_provider": settings.llm_provider,
        "llm_model": settings.active_model,
        "temperature": settings.temperature,
        "max_tokens": settings.max_tokens,
        "top_k_results": settings.top_k_results,
        "chunk_size": settings.chunk_size,
        "chunk_overlap": settings.chunk_overlap,
        "providers": {
            "nvidia":  {
                "api_key":      _mask(settings.nvidia_api_key),
                "model":        settings.nvidia_model,
                "base_url":     settings.nvidia_base_url,
                "fast_api_key": _mask(getattr(settings, "nvidia_fast_api_key", "")),
                "fast_model":   settings.nvidia_fast_model,
            },
            "openai":  {"api_key": _mask(settings.openai_api_key),   "model": settings.openai_model,   "base_url": "https://api.openai.com/v1",    "fast_api_key": "", "fast_model": ""},
            "claude":  {"api_key": _mask(settings.anthropic_api_key),"model": settings.anthropic_model, "base_url": "https://api.anthropic.com",   "fast_api_key": "", "fast_model": ""},
            "mistral": {"api_key": _mask(settings.mistral_api_key),  "model": settings.mistral_model,  "base_url": "https://api.mistral.ai/v1",    "fast_api_key": "", "fast_model": ""},
            "groq":    {"api_key": _mask(settings.groq_api_key),     "model": settings.groq_model,     "base_url": settings.groq_base_url,         "fast_api_key": "", "fast_model": settings.groq_fast_model},
            "ollama":  {"api_key": "",                                "model": settings.ollama_model,   "base_url": settings.ollama_base_url,       "fast_api_key": "", "fast_model": ""},
        },
    }


def _mask(key: str) -> str:
    """Show only last 4 chars of an API key for display."""
    if not key:
        return ""
    return f"{'*' * (len(key) - 4)}{key[-4:]}" if len(key) > 4 else "****"
