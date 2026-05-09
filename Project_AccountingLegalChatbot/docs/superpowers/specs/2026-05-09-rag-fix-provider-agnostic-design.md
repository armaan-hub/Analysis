# RAG System Fix & Provider-Agnostic Architecture Design
**Date:** 2026-05-09  
**Status:** Approved for implementation

---

## Problem Statement

The chatbot is answering legal questions using LLM training data instead of the 491 indexed documents. Specifically, a question about "Rent Payment by Cheque Bounce Law in Dubai" should cite **Federal Decree-Law No. 50 of 2022** (present in `data_source_law/DecreeLaw_50_2022_pdf.pdf`) but the LLM cited a completely wrong law (Federal Decree-Law No. 14 of 2020 — anti-money laundering). The RAG system is not being used at all.

### Root Causes (3 layers)

| Layer | Issue | Impact |
|-------|-------|--------|
| 1 | ChromaDB 1.5.8 (Rust) type incompatibility with existing data: `u64 ≠ BLOB`. Collection exists but throws `InternalError` on every query | ALL 12,376 embedded chunks unreachable → 0 RAG results |
| 2 | 170 documents (38%) failed embedding with HTTP 400. NVIDIA `nv-embedqa-e5-v5` has a 512-token limit; current chunk_size=1000 chars exceeds this for dense legal text | `DecreeLaw_50_2022_pdf.pdf` and 169 others never in vector store |
| 3 | When RAG returns 0 results, LLM answers from training data **silently** with no disclaimer | User gets confident but hallucinated law citations |

---

## Design Goals

1. **Fix RAG completely** — all 491 documents searchable and used in answers
2. **Provider-agnostic** — switch NVIDIA → Ollama → OpenAI → Claude via `.env` change, **no manual re-indexing**
3. **Auto re-embed on provider change** — system detects provider/dimension change on startup, re-embeds in background
4. **Transparency** — user always knows if answer is from documents or general knowledge
5. **Dynamic settings UI** — enter API key → auto-fetch available models as dropdown

---

## Architecture

### Component 1: Persistent Chunk Store (NEW)

Add `document_chunks` table to the database. This is the **source of truth** for all ingested text. ChromaDB becomes a fast search index only — not the data source.

```sql
CREATE TABLE document_chunks (
    id VARCHAR(36) PRIMARY KEY,
    doc_id VARCHAR(36) NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    chunk_index INTEGER NOT NULL,
    text TEXT NOT NULL,
    metadata_json JSON,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

**Why this matters:** If ChromaDB breaks or provider changes, re-embedding happens automatically from this table — no PDF re-parsing required. PDFs are only parsed once, ever.

### Component 2: Universal Provider Adapters (EXTEND)

All providers implement the same interface. The rest of the system is provider-unaware.

#### Embedding Providers
| Provider | Model | Dimension | Token Limit | Cost |
|----------|-------|-----------|-------------|------|
| `nvidia` | nv-embedqa-e5-v5 | 1024 | 512 tokens | Free tier |
| `ollama` | nomic-embed-text | 768 | ~8192 tokens | Free (local) |
| `openai` | text-embedding-3-small | 1536 | 8192 tokens | Paid |

Config: `EMBEDDING_PROVIDER=nvidia|ollama|openai` in `.env`

#### LLM Providers  
| Provider | Main Model | Fast Model | Cost |
|----------|-----------|------------|------|
| `nvidia` | mistral-large-3 | devstral-2 | Free tier |
| `ollama` | qwen3.5:35b (installed) | any local | Free (local) |
| `openai` | gpt-4o | gpt-4o-mini | Paid |
| `claude` | claude-opus-4 | claude-haiku-4 | Paid |

Config: `LLM_PROVIDER=nvidia|ollama|openai|claude` in `.env`

### Component 3: Auto Re-Embed on Provider Change

On backend startup:
1. Read stored `embedding_provider` and `embedding_dimension` from `user_settings`
2. Compare with current `EMBEDDING_PROVIDER` and its dimension
3. If mismatch detected → mark all documents as `needs_reindex` → trigger background re-embedding job that reads from `document_chunks` table
4. Store new provider and dimension in `user_settings`

This means switching providers = edit `.env` + restart → done. Zero manual work.

### Component 4: Smart Provider-Aware Chunking (FIX)

Current chunk_size=1000 chars causes 400 errors with NVIDIA (512-token limit).

```
NVIDIA:  chunk_size=350 chars, chunk_overlap=50 chars   (~250 tokens, safe under 512)
Ollama:  chunk_size=1500 chars, chunk_overlap=200 chars  (~1000 tokens, no limit concern)
OpenAI:  chunk_size=1500 chars, chunk_overlap=200 chars  (~1000 tokens, safe)
```

Provider-aware chunk sizes are set in `document_processor.py` based on `EMBEDDING_PROVIDER`.

### Component 5: Rebuild ChromaDB Index (ONE-TIME FIX)

1. Detect the `u64 ≠ BLOB` error at startup (already partially handled)
2. On detection: backup corrupted store, create fresh collection
3. Trigger bulk re-embedding of all `document_chunks` records
4. A background admin endpoint `/api/admin/reindex` can force re-index any time

### Component 6: RAG Transparency (NEW)

When RAG search returns 0 relevant results (score below threshold):
- Append disclaimer to LLM system prompt: `"⚠️ No documents found in knowledge base matching this query. Your answer is based on general legal knowledge only. Cite this limitation clearly in your response."`
- LLM response includes a visible disclaimer to user
- Backend logs the event for monitoring

### Component 7: Dynamic Settings UI (ENHANCE)

Current state: model field is a free-text input. After entering an API key, user must know exact model names.

Target state:
- Enter API key → click "Fetch Models" button (or auto-fetch on key blur) → model selector dropdown populated dynamically
- For Ollama: auto-fetch local models without key (already installed: qwen3.5:35b)
- Main model and Fast model both show dropdown lists
- Provider-specific hints: Anthropic shows Opus/Sonnet/Haiku descriptions, OpenAI shows capability notes
- "Test Connection" verifies key AND confirms selected model responds

Backend already has `/api/settings/providers/{provider}/models` endpoint. Frontend needs:
1. Auto-trigger model fetch when provider is selected (if key already configured)
2. Show models as `<select>` dropdown instead of `<input>` text field when models list is populated
3. Add Anthropic to model fetch endpoint (currently missing — returns static list)
4. Add Ollama to model fetch (calls `http://localhost:11434/api/tags`)

---

## Implementation Phases

### Phase 1: Fix ChromaDB & Re-Index (Critical Path)
- Add `document_chunks` table migration
- Fix `_repair_legacy_index_metadata` to handle the 1.5.8 `u64 ≠ BLOB` error
- Force rebuild ChromaDB collection from scratch
- Re-process all 170 failed documents with correct chunk sizes

### Phase 2: Ollama Provider Support
- Add `OllamaEmbeddingProvider` to `rag_engine.py`
- Add Ollama chat provider to `llm_manager.py`
- Add `EMBEDDING_PROVIDER` and `OLLAMA_EMBED_MODEL` to config
- Update `.env` template

### Phase 3: Auto Re-Embed on Provider Change
- Add provider fingerprint to `user_settings`
- Startup check in `rag_engine.py`
- Background re-embedding job

### Phase 4: RAG Transparency
- Modify `chat.py` stream handler to add disclaimer when `_search_results` is empty
- Add "Based on general knowledge" badge in frontend when no sources

### Phase 5: Dynamic Settings UI
- Frontend: model dropdown auto-populate
- Backend: add Anthropic model fetch, fix Ollama model fetch
- Auto-fetch on provider switch when key is configured

---

## Testing Plan

1. Upload `DecreeLaw_50_2022_pdf.pdf` → verify chunk count > 0 in `document_chunks` table
2. Query "cheque bounce rent Dubai law" → verify sources include `DecreeLaw_50_2022_pdf.pdf`
3. Query with no matching docs → verify disclaimer appears in response
4. Switch `EMBEDDING_PROVIDER=ollama` → restart → verify auto-reindex runs
5. Settings page: enter Anthropic key → verify Opus/Sonnet/Haiku appear as dropdown
6. Settings page: select Ollama → verify qwen3.5:35b appears in model list

---

## Files Changed

| File | Change |
|------|--------|
| `backend/core/rag_engine.py` | Add OllamaEmbeddingProvider, fix ChromaDB corruption handling, add auto-reindex |
| `backend/core/document_processor.py` | Provider-aware chunk sizes |
| `backend/db/models.py` | Add DocumentChunk model |
| `backend/db/migrations/` | Add document_chunks migration |
| `backend/api/settings.py` | Add Anthropic model fetch, fix Ollama model fetch |
| `backend/config.py` | Add EMBEDDING_PROVIDER, OLLAMA_EMBED_MODEL, OLLAMA_BASE_URL |
| `frontend/src/pages/SettingsPage.tsx` | Model dropdown auto-populate |
| `backend/llm_manager.py` or `backend/core/llm_manager.py` | Add Ollama LLM provider |
