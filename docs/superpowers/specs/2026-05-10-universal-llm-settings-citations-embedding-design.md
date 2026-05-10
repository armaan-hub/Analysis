# Universal LLM Settings, RAG Citations, API Key Visibility & Embedding Status

**Date:** 2026-05-10
**Status:** Draft
**Type:** Feature design

---

## 1. Universal Adaptive LLM Settings

### 1.1 Problem

Current settings use hardcoded temperature and max_tokens across all providers. Local models (Ollama, LM Studio) receive truncated/incomplete answers due to suboptimal token budgets and timeout configurations. Cloud models also lack optimal per-family tuning.

### 1.2 Solution

Extend the existing context window registry in `llm_manager.py` with per-model-family optimal parameters. Add a `compute_llm_params(model_name)` method on the `Settings` class that detects the model family from the name and returns optimal temperature, max_tokens, and timeout.

### 1.3 Implementation

**Model family registry** in `config.py`:

| Model family (name contains) | Temperature | Max output tokens | Default timeout |
|---|---|---|---|
| `claude` | 0.3 | 4096 | 60s |
| `gpt-4` | 0.3 | 4096 | 60s |
| `gpt-3.5` | 0.4 | 2048 | 30s |
| `ollama` | 0.3 | 4096 | 120s |
| `lmstudio`, `lm-studio` | 0.3 | 4096 | 180s |
| `mistral` | 0.25 | 4096 | 60s |
| `groq` | 0.3 | 4096 | 30s |
| `nvidia` | 0.3 | 4096 | 60s |
| `default` | 0.3 | 4096 | 60s |

**New method on `Settings`:**
```python
def compute_llm_params(self, model_name: str) -> dict:
    """Return optimal params for any model family."""
    # Detect family from model_name substring match
    # Return {temperature, max_tokens, timeout_seconds}
```

**Timeout strategy:**
- Streaming: no read timeout (TTFB for local models can be 60-90s)
- Non-streaming: computed from model family (30s for fast, 180s for local)
- All providers use httpx timeouts derived from this method

**Backward compatibility:** Existing callers that pass explicit temperature/max_tokens continue to work. New code uses `compute_llm_params()` as the default path.

---

## 2. RAG Citation System

### 2.1 Problem

When the LLM answers a question using retrieved RAG chunks, it does not cite the source documents. The user has no way to verify which PDF/chunk the answer came from. With NVIDIA API, the model attempts citations but cites the wrong document entirely.

### 2.2 Solution

Two-layer fix:
1. **Metadata enrichment:** RAG `retrieve()` returns chunks with full metadata (filename, page, chunk_id)
2. **Citation enforcement:** System prompt instructs the LLM to cite sources inline; a fallback post-processor inserts source tags if the model doesn't cite

### 2.3 Implementation

**Chunk metadata schema:**
Each retrieved chunk already carries metadata. Ensure all retrievers (HybridRetriever, GraphRAG) return:
```python
{
    "text": "...",           # chunk text
    "chunk_id": "uuid",      # unique chunk identifier
    "source_file": "contract.pdf",  # original filename
    "page": 3,               # page number (if available)
    "score": 0.95,           # relevance score
    "document_id": "..."     # internal document ID
}
```

**System prompt injection in `chat.py`:**
```
You are a helpful legal/accounting assistant. You answers must always cite your sources.

When answering, use the following format for each piece of information drawn from the retrieved documents:
📄 [filename] (page N)

Example: "The fee for bounced cheques is AED 50 per incident 📄 Banking_Law_UAE.pdf (page 12)."

If you are unsure about something, say so rather than guessing.
```

**Post-processor fallback:**
If the LLM response contains no citation markers, a post-processing step scans the response for claims and attaches the top-scoring source chunk's metadata as a footer:
```
Sources consulted:
- 📄 contract_FZ_2024.pdf (page 3) — relevance: 95%
- 📄 invoice_policy.pdf (page 7) — relevance: 82%
```

**Citation format:**
- Inline: `📄 filename.pdf (page N)`
- Footer: list of all consulted sources with relevance scores
- Error case: if retrieval returns 0 chunks, answer normally with "I couldn't find relevant documents to answer this question."

### 2.4 Scope boundaries

- Citations work for RAG-powered answers only
- Non-RAG responses (general conversation, no retrieval) do not include citations
- GraphRAG and HybridRetriever both feed into the same citation pipeline

---

## 3. Per-Key API Key Visibility

### 3.1 Problem

API keys are saved correctly to `.env` via `_update_env_key()`, but after saving they disappear from the Streamlit UI. Users cannot verify whether a key is configured without checking the `.env` file directly.

### 3.2 Solution

Add a visibility flag per API key stored in a separate `settings_keys.json` file (gitignored). The UI respects these flags to display keys as masked, hidden, or not shown.

### 3.3 Implementation

**Settings file:** `backend/api/settings_keys.json` (created if not exists, gitignored)

```json
{
  "NVIDIA_API_KEY": {"visibility": "masked"},
  "ANTHROPIC_API_KEY": {"visibility": "masked"},
  "OPENAI_API_KEY": {"hidden"},
  "MISTRAL_API_KEY": {"hidden"},
  "GROQ_API_KEY": {"hidden"}
}
```

**Visibility levels:**
- `masked`: Display `•••••••••` + green "Configured" badge
- `hidden`: Display only green "Configured" badge (no text)
- `none`: Not displayed at all

**Settings UI:**
- Each API key field has a small eye/visibility toggle icon (👁) next to it
- Clicking cycles: `hidden` → `masked` → `none` → `hidden`
- Default for new keys: `masked`
- Changing visibility updates `settings_keys.json` (not `.env`)

**API for visibility:**
- `GET /api/settings/keys` — returns visibility config (no key values)
- `PUT /api/settings/keys/{key_name}` — update visibility for a specific key

**Persistence:**
- API keys still write to `.env` as before (backend config)
- Visibility flags write to `settings_keys.json` (UI config)

---

## 4. Embedding Provider UI with Live Status

### 4.1 Problem

The embedding provider setting (NVIDIA/OpenAI/Ollama) is only configurable via `.env` edit. The current UI shows the provider name and fingerprint but the status (whether it's actually working) is unclear. No way to switch providers from the UI.

### 4.2 Solution

A settings card component showing:
- Current provider with a live status dot
- Dropdown to switch between NVIDIA / OpenAI / Ollama
- Live probe on page load confirms endpoint connectivity
- Switching triggers re-index confirmation if fingerprint changes

### 4.3 Implementation

**Status probing:**
```python
def probe_embedding_provider(provider: str) -> dict:
    """Ping the embedding endpoint to check connectivity."""
    # NVIDIA: POST to NVIDIA NIM endpoint
    # OpenAI: POST to OpenAI embeddings endpoint
    # Ollama: POST to Ollama /api/embeddings
    # Returns: {status: "connected" | "failed", latency_ms: int, error: str}
```

**Status dot logic:**
- 🟢 Green: endpoint responds within 5s
- 🟡 Yellow: responds but slow (>5s)
- 🔴 Red: no response / error

**Provider card in UI:**
```
┌─────────────────────────────────────────┐
│ Embedding Provider                      │
│ [Nvidia ▼]  🟢 Connected                │
│ Model: nvidia/nv-embed-qa               │
│ Dimension: 1024 | Chunks: 1,247          │
└─────────────────────────────────────────┘
```

**Switch confirmation:**
- If new provider's fingerprint differs from current vector store fingerprint → "Changing provider will require re-indexing all documents. This may take several minutes. Proceed?"
- Re-index triggers background job with progress indicator

**API endpoints:**
- `GET /api/settings/embedding-status` — returns current provider, model, status, document count
- `POST /api/settings/embedding-switch` — switch provider, trigger re-index if needed

---

## 5. File Changes Summary

| File | Change |
|---|---|
| `backend/config.py` | Add `compute_llm_params()` method with model family registry |
| `backend/api/chat.py` | Inject citation format into system prompt; add post-processor |
| `backend/core/rag_engine.py` | Ensure all retrievers return full metadata (source_file, page, chunk_id) |
| `backend/api/settings.py` | Add keys visibility API endpoints |
| `backend/api/settings_keys.json` | New file: per-key visibility flags (gitignored) |
| `frontend/` | Add embedding provider card with dropdown + status dots; add eye toggle on API key fields |

---

## 6. Testing Strategy

- Unit tests for `compute_llm_params()` with all model families
- Integration test: RAG retrieval returns metadata → LLM cites in answer
- API tests: visibility flags save/load correctly
- E2E: switch embedding provider, confirm re-index prompt appears
- Verify: with LM Studio + citations enabled, model returns answers with `📄 filename.pdf (page N)` format

---

## 7. Out of Scope

- Changing the RAG retrieval algorithm (HybridRetriever / GraphRAG stays as-is)
- Modifying the chunking strategy
- Supporting additional embedding providers beyond NVIDIA/OpenAI/Ollama
- Non-RAG citation for general conversation