# Smart LLM Auto-Detection Design

**Date:** 2026-05-10  
**Status:** Approved  
**Feature:** Auto-detect local (Ollama, LM Studio, HuggingFace TGI, Kobold.cpp) and cloud (OpenAI, Anthropic, etc.) LLM providers from URL and API key, with a unified "Local Models" UI group.

---

## 1. Problem Statement

Currently, the chatbot only has a fixed list of hardcoded providers. If the user has Ollama running with a non-default model, or starts LM Studio, the UI does not pick it up automatically. The user must manually configure base URLs and model names.

The goal is to:
1. **Auto-scan localhost ports** at startup and on-demand to discover running local inference servers.
2. **Identify the provider from the base URL** (not just the API key prefix).
3. **Expose a "Local Models" group** in the sidebar settings panel, showing each discovered server with a live status dot and a refresh button.
4. **Activate Ollama with `qwen3.5:35b-a3b-coding-nvfp4`** immediately (already done via .env).

---

## 2. Architecture Overview

```
Frontend (Settings sidebar)
  └── "Local Models" group
        ├── Ollama  ●  (3 models) [Activate]
        ├── LM Studio  ○  (offline) 
        └── [↺ Re-scan]

  └── "Cloud Providers" group
        ├── NVIDIA NIM  ✅ ACTIVE
        ├── OpenAI  ○  [Add Key]
        └── Anthropic  ○  [Add Key]

Backend
  ├── GET  /api/settings/local-scan          → current scan results
  ├── POST /api/settings/local-scan/refresh  → trigger fresh scan
  └── POST /api/settings/detect-provider     → URL → provider name + key env var hint

Core
  └── backend/core/local_scanner.py          ← NEW
        LocalServerScanner
          scan_all()   → List[LocalServer]
          probe(url)   → ServerInfo | None
```

---

## 3. LocalServerScanner (backend/core/local_scanner.py)

### 3.1 Probe targets

| Port  | Provider        | Health endpoint            | Models endpoint         |
|-------|-----------------|----------------------------|-------------------------|
| 11434 | Ollama          | `/api/tags`                | `/api/tags` (`.models`) |
| 1234  | LM Studio       | `/v1/models`               | `/v1/models` (`.data`)  |
| 8080  | HuggingFace TGI | `/health`                  | `/v1/models`            |
| 5001  | Kobold.cpp      | `/api/v1/info`             | `/api/v1/model`         |

### 3.2 Probe logic

```python
@dataclass
class LocalServer:
    provider: str           # "ollama" | "lmstudio" | "tgi" | "kobold"
    base_url: str
    online: bool
    models: list[str]
    latency_ms: int

async def _probe_one(url: str, provider: str, ...) -> LocalServer
async def scan_all(timeout_s: float = 1.0) -> list[LocalServer]
```

- All probes run **in parallel** via `asyncio.gather`.
- Each probe has a **1-second timeout** to keep startup fast.
- Results are **cached for 60 seconds** to avoid repeated probes on each settings page open.
- On startup, `scan_all()` is called in the background task pool (non-blocking).

### 3.3 URL-based provider identification

When a user enters a custom base URL, the backend identifies the provider by matching URL patterns:

| URL pattern              | Provider   | Required env var hint  |
|--------------------------|------------|------------------------|
| `*anthropic.com*`        | claude     | `ANTHROPIC_API_KEY`    |
| `*openai.com*`           | openai     | `OPENAI_API_KEY`       |
| `*nvidia.com*` / `*nim*` | nvidia     | `NVIDIA_API_KEY`       |
| `*mistral.ai*`           | mistral    | `MISTRAL_API_KEY`      |
| `*groq.com*`             | groq       | `GROQ_API_KEY`         |
| `localhost:11434`        | ollama     | *(none needed)*        |
| `localhost:1234`         | lmstudio   | *(none needed)*        |
| `*` (other localhost)    | custom     | *(user supplies)*      |

The `POST /api/settings/detect-provider` endpoint:
- Input: `{ "base_url": "https://api.openai.com/v1" }`
- Output: `{ "provider": "openai", "key_env_var": "OPENAI_API_KEY", "key_label": "OpenAI API Key" }`

---

## 4. LocalProvider class (backend/core/llm_manager.py)

A single `LocalProvider` wraps **any OpenAI-compatible local server** (LM Studio, TGI, Kobold, custom Ollama OpenAI-compat endpoint):

```python
class LocalProvider(BaseLLMProvider):
    def __init__(self, base_url: str, model: str, api_key: str = "sk-local"):
        ...
    async def chat(self, messages, **kwargs) -> str:
        # POST {base_url}/v1/chat/completions
```

- Ollama's native API (`/api/generate`, `/api/chat`) is already handled by `OllamaProvider`.
- `LocalProvider` is used for LM Studio, TGI, Kobold — all speak `/v1/chat/completions`.
- `api_key` defaults to `"sk-local"` (required by OpenAI client but ignored by local servers).

---

## 5. API Endpoints

### GET /api/settings/local-scan
Returns cached scan results. 200 always (even if all offline).
```json
{
  "scan_time": "2026-05-10T10:31:00Z",
  "cache_age_s": 12,
  "servers": [
    { "provider": "ollama", "base_url": "http://localhost:11434", "online": true,
      "models": ["qwen3.5:35b-a3b-coding-nvfp4", "nomic-embed-text:latest"], "latency_ms": 4 },
    { "provider": "lmstudio", "base_url": "http://localhost:1234", "online": false,
      "models": [], "latency_ms": 0 }
  ]
}
```

### POST /api/settings/local-scan/refresh
Triggers a fresh scan, invalidates cache, returns new results. Same schema as GET.

### POST /api/settings/detect-provider
```json
// Request
{ "base_url": "https://api.openai.com/v1", "api_key": "sk-..." }

// Response
{ "provider": "openai", "key_env_var": "OPENAI_API_KEY",
  "key_label": "OpenAI API Key", "key_valid": true }
```
`key_valid` is set by a lightweight test call (`/v1/models` or equivalent).

---

## 6. Frontend Changes

### 6.1 "Local Models" sidebar group

A new collapsible section in the settings panel above "Cloud Providers":

```
┌─────────────────────────────────────┐
│ Local Models                    [↺] │
├─────────────────────────────────────┤
│ ● Ollama  (2 models)   [Activate ▾] │
│   └ qwen3.5:35b-a3b-coding-nvfp4   │
│   └ nomic-embed-text:latest          │
│ ○ LM Studio  (offline)               │
│ ○ HuggingFace TGI  (offline)        │
└─────────────────────────────────────┘
```

- Green dot `●` = online, grey `○` = offline.
- `[↺]` button calls `POST /api/settings/local-scan/refresh`.
- `[Activate ▾]` dropdown lets user pick a model and set it as active.
- Section is shown even when all servers are offline (to allow discovery).

### 6.2 "Add Provider" URL+key flow

When user enters a custom URL in the existing "Add Provider" form:
1. Frontend calls `POST /api/settings/detect-provider` on blur.
2. Provider name and key label are auto-filled below the URL field.
3. User enters key → form validates live.
4. Submit saves to `.env` and restarts the provider.

---

## 7. Startup Integration

In `backend/main.py`, add to the startup task sequence:

```python
from core.local_scanner import LocalServerScanner

@app.on_event("startup")
async def startup():
    ...
    # Non-blocking background scan
    asyncio.create_task(LocalServerScanner().scan_all())
```

The scan result is stored in `LocalServerScanner._cache` (module-level singleton). First request to `GET /api/settings/local-scan` within 60s returns the cached result; after that a background refresh kicks off automatically.

---

## 8. Config Changes (backend/config.py)

```python
# New fields
local_scan_ports: list[int] = [11434, 1234, 8080, 5001]
local_scan_timeout_s: float = 1.0
local_scan_cache_ttl_s: int = 60
```

---

## 9. Error Handling

| Scenario                              | Behavior                                          |
|---------------------------------------|---------------------------------------------------|
| Local server offline at startup       | Marked offline in cache; no error logged          |
| Local server goes offline mid-session | Next scan marks offline; active model switches to fallback |
| Provider detect URL unrecognized      | Returns `{ "provider": "custom" }` — user fills in key label manually |
| key_valid check fails (bad key)       | Returns `{ "key_valid": false, "error": "401 Unauthorized" }` |
| Fresh scan takes >1s                  | Probe times out; server marked offline for that cycle |

---

## 10. Testing Plan

- Unit: `LocalServerScanner.probe()` with mock HTTP responses (online/offline/timeout)
- Unit: `detect_provider_from_url()` against all URL patterns
- Integration: `GET /api/settings/local-scan` returns 200 with correct schema
- Integration: `POST /local-scan/refresh` triggers re-probe
- E2E: Start Ollama, call refresh, verify `qwen3.5:35b-a3b-coding-nvfp4` appears in response
- E2E: Activate Ollama model via API, send chat message, verify Ollama is called (log check)

---

## 11. Implementation Order

1. `backend/core/local_scanner.py` — `LocalServerScanner` + `LocalServer` dataclass
2. `backend/api/settings.py` — 3 new endpoints
3. `backend/core/llm_manager.py` — `LocalProvider` class + register in `_PROVIDER_MAP`
4. `backend/main.py` — startup scan task
5. `backend/config.py` — new config fields
6. Frontend — "Local Models" sidebar group
7. Frontend — URL auto-detect in "Add Provider" form
8. Tests — unit + integration + E2E

---

## 12. Out of Scope

- Automatic installation of Ollama or LM Studio
- GPU/VRAM detection
- Streaming token display per-provider (already handled by existing SSE layer)
- Model download UI
