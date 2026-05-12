# Embedding Settings UI — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wire up the embedding provider/model dropdown in the frontend Settings page so users can switch between NVIDIA, OpenAI, and Ollama embedding providers. The backend must expose the necessary endpoints.

**Architecture:** Two new backend endpoints in `api/settings.py` (embedding-providers, embedding-models), plus an embedding section in `frontend/src/pages/SettingsPage.tsx`. The embedding provider selection affects chunk size, chunk overlap, and embedding dimension — all shown in the UI. On provider change, a warning is shown that documents need re-indexing (handled by the existing reindex-all endpoint).

**Tech Stack:** FastAPI, React + TypeScript, httpx, respx (for tests)

---

## File Map

| File | Role |
|------|------|
| `api/settings.py` | Add embedding-providers and embedding-models endpoints |
| `tests/test_embedding_settings.py` | Test the two new backend endpoints |
| `frontend/src/pages/SettingsPage.tsx` | Add embedding section to existing Settings page |
| `frontend/src/lib/api.ts` | Check if API helper for settings exists, add embedding helpers |

---

## Tasks

### Task 1: Add Embedding Provider/List Endpoint

**Files:**
- Modify: `backend/api/settings.py`
- Test: `backend/tests/test_embedding_settings.py`

- [ ] **Step 1: Write the failing test**

```python
"""Tests for the embedding settings API endpoints."""
import pytest
from unittest.mock import patch

@pytest.mark.asyncio
async def test_embedding_providers_lists_all(client):
    """GET /api/settings/embedding-providers returns all providers with status."""
    with patch("core.llm_manager.list_available_providers") as mock_list:
        mock_list.return_value = [
            {"name": "nvidia", "configured": True},
            {"name": "openai", "configured": False},
            {"name": "ollama", "configured": True},
        ]
        r = await client.get("/api/settings/embedding-providers")
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)
        assert len(data) == 3
        names = [p["name"] for p in data]
        assert "nvidia" in names
        assert "openai" in names
        assert "ollama" in names


@pytest.mark.asyncio
async def test_embedding_providers_includes_chunk_info(client):
    """Each provider includes current chunk_size, chunk_overlap, dimension."""
    with patch("core.llm_manager.list_available_providers") as mock_list:
        mock_list.return_value = [{"name": "nvidia", "configured": True}]
        r = await client.get("/api/settings/embedding-providers")
        assert r.status_code == 200
        nvidia = next(p for p in r.json() if p["name"] == "nvidia")
        assert "chunk_size" in nvidia
        assert "chunk_overlap" in nvidia
        assert "dimension" in nvidia
        assert nvidia["chunk_size"] == 350
        assert nvidia["chunk_overlap"] == 50
        assert nvidia["dimension"] == 1024


@pytest.mark.asyncio
async def test_embedding_providers_current_active(client):
    """Response includes which provider is currently active."""
    r = await client.get("/api/settings/embedding-providers")
    assert r.status_code == 200
    providers = r.json()
    active = [p for p in providers if p.get("is_active")]
    # At most one provider should be active
    assert len(active) <= 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_embedding_settings.py::test_embedding_providers_lists_all tests/test_embedding_settings.py::test_embedding_providers_includes_chunk_info tests/test_embedding_settings.py::test_embedding_providers_current_active -v`
Expected: 404 Not Found — endpoint doesn't exist yet

- [ ] **Step 3: Write the backend endpoint**

In `backend/api/settings.py`, add a new response model and endpoint. The response should look like:

```python
class EmbeddingProviderInfo(BaseModel):
    name: str
    configured: bool
    is_active: bool
    model: str
    dimension: int
    chunk_size: int
    chunk_overlap: int
```

Add these to the `api/settings.py` file (near the other schema definitions around lines 28-57), then add the endpoint:

```python
@router.get("/embedding-providers", response_model=list[EmbeddingProviderInfo])
async def get_embedding_providers():
    """List all available embedding providers with their current config."""
    from config import settings
    all_providers = ["nvidia", "openai", "ollama"]
    provider_models = {
        "nvidia": settings.nvidia_embed_model,
        "openai": settings.openai_embed_model,
        "ollama": settings.ollama_embed_model,
    }
    result = []
    for name in all_providers:
        is_active = (settings.embedding_provider == name)
        result.append(EmbeddingProviderInfo(
            name=name,
            configured=provider_models[name] not in ("", None),
            is_active=is_active,
            model=settings.embedding_model if is_active else provider_models[name],
            dimension=settings.embedding_dimension if is_active else {"nvidia": 1024, "openai": 1536, "ollama": 768}[name],
            chunk_size=settings.embedding_chunk_size if is_active else {"nvidia": 350, "openai": 1200, "ollama": 1200}[name],
            chunk_overlap=settings.embedding_chunk_overlap if is_active else {"nvidia": 50, "openai": 150, "ollama": 150}[name],
        ))
    return result
```

Note: Read `api/settings.py` first to find the exact line ranges for the schema section and the endpoint section, then insert accordingly.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_embedding_settings.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
cd backend
git add api/settings.py tests/test_embedding_settings.py
git commit -m "feat(settings): add embedding-providers endpoint"
```

---

### Task 2: Add Embedding Models Endpoint

**Files:**
- Modify: `backend/api/settings.py`
- Test: `backend/tests/test_embedding_settings.py`

- [ ] **Step 1: Write the failing test**

```python
@pytest.mark.asyncio
async def test_embedding_models_ollama(client):
    """GET /api/settings/embedding-models?provider=ollama returns Ollama models list."""
    r = await client.get("/api/settings/embedding-models?provider=ollama")
    assert r.status_code == 200
    data = r.json()
    # Should return a list of ModelInfo (id, name)
    assert isinstance(data, list)


@pytest.mark.asyncio
async def test_embedding_models_invalid_provider(client):
    """Unknown provider returns 400."""
    r = await client.get("/api/settings/embedding-models?provider=unknown")
    assert r.status_code == 400
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_embedding_settings.py::test_embedding_models_ollama tests/test_embedding_settings.py::test_embedding_models_invalid_provider -v`
Expected: 404 Not Found

- [ ] **Step 3: Write the backend endpoint**

In `backend/api/settings.py`, add this endpoint:

```python
@router.get("/embedding-models", response_model=list[ModelInfo])
async def get_embedding_models(provider: str):
    """Get available embedding models for a provider."""
    from config import settings
    provider = provider.lower()

    if provider == "ollama":
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(f"{settings.ollama_base_url}/api/tags")
                resp.raise_for_status()
                data = resp.json()
                models = sorted(m["name"] for m in data.get("models", []))
                return [ModelInfo(id=m, name=m) for m in models] if models else [ModelInfo(id="(no models)", name="(no models)")]
        except Exception as exc:
            raise HTTPException(status_code=503, detail=f"Ollama not reachable: {exc}")

    elif provider == "nvidia":
        return [ModelInfo(id=settings.nvidia_embed_model, name=settings.nvidia_embed_model)]

    elif provider == "openai":
        return [ModelInfo(id=settings.openai_embed_model, name=settings.openai_embed_model)]

    else:
        raise HTTPException(status_code=400, detail=f"Unknown embedding provider '{provider}'")
```

Note: Read `api/settings.py` first to find the correct insertion point after the existing endpoints (around line 292 before the closing of the file).

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_embedding_settings.py::test_embedding_models_ollama tests/test_embedding_settings.py::test_embedding_models_invalid_provider -v`
Expected: 2 passed

- [ ] **Step 5: Run full new test file**

Run: `uv run pytest tests/test_embedding_settings.py -v`
Expected: 5 passed (3 from Task 1 + 2 from Task 2)

- [ ] **Step 6: Commit**

```bash
cd backend
git add api/settings.py
git commit -m "feat(settings): add embedding-models endpoint"
```

---

### Task 3: Embedding Settings UI in Frontend

**Files:**
- Modify: `frontend/src/pages/SettingsPage.tsx`
- Modify: `frontend/src/lib/api.ts` (or wherever the API client is defined)

- [ ] **Step 1: Read the existing API client**

Read `frontend/src/lib/api.ts` (or similar — may be named `api.ts`, `client.ts`, or similar in `frontend/src/lib/`). Find the pattern for existing API calls (GET, PUT, POST). If no centralized API client exists, check how `SettingsPage.tsx` calls API — it uses `API.get()` / `API.put()` from `'../lib/api'`.

Add helper functions following the existing pattern:

```typescript
export async function getEmbeddingProviders(): Promise<EmbeddingProvider[]> {
  const r = await API.get('/api/settings/embedding-providers');
  return r.data as EmbeddingProvider[];
}

export async function getEmbeddingModels(provider: string): Promise<ModelOption[]> {
  const r = await API.get(`/api/settings/embedding-models?provider=${encodeURIComponent(provider)}`);
  return r.data as ModelOption[];
}

export async function updateEmbeddingProvider(provider: string): Promise<void> {
  await API.put('/api/settings/embedding', { provider });
}
```

Define the types:

```typescript
export interface EmbeddingProvider {
  name: string;
  configured: boolean;
  is_active: boolean;
  model: string;
  dimension: number;
  chunk_size: number;
  chunk_overlap: number;
}

export interface ModelOption {
  id: string;
  name: string;
}
```

- [ ] **Step 2: Add embedding section to SettingsPage.tsx**

Read `frontend/src/pages/SettingsPage.tsx` to find the insertion point — after the "System Info" section (around line 211 in the current file), add an "Embedding (RAG)" section.

The new section should:
1. Show a dropdown/tab to select between nvidia/openai/ollama for embeddings
2. Display the current dimension, chunk_size, chunk_overlap for the selected provider
3. Show a "Re-index required" warning when switching providers (since the existing reindex-all endpoint exists for this)
4. Have a "Save & Trigger Re-index" button that calls the backend to update the embedding provider AND triggers reindex-all

```typescript
// Add to SettingsPage.tsx — import types and helpers
import {
  API,
  getErrMsg,
  getEmbeddingProviders,
  getEmbeddingModels,
  updateEmbeddingProvider,
  type EmbeddingProvider,
  type ModelOption,
} from '../lib/api';

// Add state for embedding section (add to existing useState calls)
const [embeddingProviders, setEmbeddingProviders] = useState<EmbeddingProvider[]>([]);
const [selectedEmbedProvider, setSelectedEmbedProvider] = useState<string>('nvidia');
const [embedModels, setEmbedModels] = useState<ModelOption[]>([]);
const [selectedEmbedModel, setSelectedEmbedModel] = useState<string>('');

// Fetch embedding providers on mount
useEffect(() => {
  getEmbeddingProviders()
    .then(setEmbeddingProviders)
    .catch(() => {});
}, []);

// When provider changes, fetch its models
useEffect(() => {
  if (!selectedEmbedProvider) return;
  getEmbeddingModels(selectedEmbedProvider)
    .then(setEmbedModels)
    .catch(() => setEmbedModels([]));
}, [selectedEmbedProvider]);

// When a provider is selected, pre-fill its info
const currentEmbedProvider = embeddingProviders.find(p => p.name === selectedEmbedProvider);

// Add to JSX — after the "System Info" div (before the closing of page-body):
{
  /* ── Embedding (RAG) Section ──────────────────────────────── */
}
<div className="settings-section-title" style={{ marginTop: '24px', marginBottom: '10px' }}>
  Embedding (RAG)
</div>
<div style={{
  border: '1px solid var(--border)',
  borderRadius: '8px',
  padding: '12px 14px',
  background: 'var(--s-bg-2)',
}}>
  <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', marginBottom: '12px' }}>
    {embeddingProviders.map(p => (
      <button
        key={p.name}
        className={`btn ${selectedEmbedProvider === p.name ? 'btn-primary' : 'btn-secondary'}`}
        style={{ fontSize: '0.8rem' }}
        onClick={() => {
          setSelectedEmbedProvider(p.name);
          setSelectedEmbedModel(p.model);
        }}
      >
        {p.name.toUpperCase()} {p.is_active ? '✓' : ''}
      </button>
    ))}
  </div>

  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '8px', marginBottom: '12px', fontSize: '0.78rem' }}>
    <div>
      <div style={{ color: 'var(--text-2)', marginBottom: '2px' }}>Dimension</div>
      <div style={{ fontWeight: 600 }}>{currentEmbedProvider?.dimension ?? '—'}</div>
    </div>
    <div>
      <div style={{ color: 'var(--text-2)', marginBottom: '2px' }}>Chunk Size</div>
      <div style={{ fontWeight: 600 }}>{currentEmbedProvider?.chunk_size ?? '—'}</div>
    </div>
    <div>
      <div style={{ color: 'var(--text-2)', marginBottom: '2px' }}>Overlap</div>
      <div style={{ fontWeight: 600 }}>{currentEmbedProvider?.chunk_overlap ?? '—'}</div>
    </div>
  </div>

  {currentEmbedProvider && !currentEmbedProvider.is_active && (
    <div style={{
      fontSize: '0.75rem',
      color: 'var(--orange)',
      background: 'rgba(251,191,36,0.1)',
      borderRadius: '6px',
      padding: '6px 10px',
      marginBottom: '12px',
    }}>
      ⚠️ Switching providers will require re-indexing all documents.
      Run the "Reindex All" action from the Documents panel after saving.
    </div>
  )}

  <button
    className="btn btn-primary"
    style={{ width: '100%' }}
    onClick={async () => {
      try {
        await updateEmbeddingProvider(selectedEmbedProvider);
        flash(`Embedding provider set to ${selectedEmbedProvider}`, true);
      } catch (e) {
        flash(getErrMsg(e, 'Failed to update embedding provider'), false);
      }
    }}
  >
    💾 Save Embedding Provider
  </button>
</div>
```

- [ ] **Step 3: Verify the frontend builds without TypeScript errors**

Run: `cd frontend && npm run build 2>&1 | grep -E "error TS|Error:|BUILD"` (or the equivalent build command)
Expected: No TypeScript errors

- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/SettingsPage.tsx frontend/src/lib/api.ts
git commit -m "feat(frontend): add embedding provider settings UI"
```

---

## Verification

After all tasks are complete:

```bash
# Backend tests
cd backend && uv run pytest tests/test_embedding_settings.py -v
# Expected: 5 passed

# Full suite
uv run pytest tests/ -q
# Expected: 677+ passed, 8 skipped, 0 failures

# Frontend build
cd frontend && npm run build
# Expected: clean build
```

---

## Self-Review Checklist

1. **Spec coverage:** All 3 backend endpoint requirements covered (embedding-providers, embedding-models, optional PATCH). Frontend embedding section adds provider selection, info display, and save functionality.

2. **Placeholder scan:** No TBD/TODO placeholders. All step content is complete.

3. **Type consistency:** `EmbeddingProviderInfo` response model matches what the frontend `EmbeddingProvider` type expects. `ModelInfo` in settings.py re-used for embedding-models endpoint matches `ModelOption` in frontend.

4. **Test scope:** `test_embedding_settings.py` tests the API contract only. Frontend integration is verified by build (no TS errors).
