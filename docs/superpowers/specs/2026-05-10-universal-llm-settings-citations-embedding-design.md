# Universal LLM Settings, RAG Citations, API Key Visibility & Embedding Status

**Date:** 2026-05-10
**Updated:** 2026-05-10 (mode-specific design)
**Status:** Draft
**Type:** Feature design

---

## Overview

The system operates in **three distinct modes**, each with different token budgets, timeout requirements, data sources, and response patterns. The design below addresses all three.

---

## Modes Overview

| Mode | Use case | Data sources | Response type | Token budget | Timeout |
|---|---|---|---|---|---|
| **Fast** | Quick Q&A | RAG (local docs only) | Streaming answer | Medium | Medium |
| **Deep Research** | Comprehensive research | Web + RAG (local docs) | Full report/thesis | Maximum | Long |
| **Analysis** | Document-heavy analysis | User uploads + RAG | Structured report | Maximum | Very long |

---

## 1. Universal Adaptive LLM Settings

### 1.1 Problem

Current settings use hardcoded temperature and max_tokens across all providers and modes. Local models (Ollama, LM Studio) receive truncated/incomplete answers due to suboptimal token budgets and timeout configurations.

### 1.2 Solution

Per-mode, per-model-family parameter registry. `compute_llm_params(model_name, mode)` detects model family and returns optimal temperature, max_tokens, and timeout for the given mode.

### 1.3 Per-Mode Token Budgets

| Mode | Fast token budget | Deep Research / Analysis token budget | Notes |
|---|---|---|---|
| **claude** | 4096 | 32768 | Analysis/deep can reach 32K |
| **gpt-4** | 4096 | 32768 | GPT-4o supports 128K context |
| **gpt-3.5** | 2048 | 8192 | Smaller model family |
| **ollama** | 8192 | 32768 | Local — needs headroom for complex output |
| **lmstudio** | 8192 | 32768 | Local GPU — maximum output for analysis |
| **mistral** | 8192 | 32768 | NVIDIA NIM large models |
| **groq** | 4096 | 16384 | Fast API tier |
| **nvidia** | 8192 | 32768 | NVIDIA NIM hosted models |
| **default** | 4096 | 16384 | Fallback for unknown models |

### 1.4 Per-Mode Timeout Strategy

| Mode | Timeout behavior |
|---|---|
| **Fast** | Streaming only — no read timeout (TTFB for local models 5-60s). Non-streaming capped at 30s. |
| **Deep Research** | No streaming. Non-streaming: 300s for cloud models, 600s for local models. Takes time to browse web, synthesize findings, generate long report. |
| **Analysis** | No streaming. Non-streaming: 600s for cloud models, 900s for local models. Must process user-uploaded documents (trial balance, ledgers, MOA), run multi-step financial/legal analysis. |
| **All modes** | Connect timeout: 10s. Write timeout: 10s. |

### 1.5 Temperature by Mode

| Mode | Temperature | Reasoning |
|---|---|---|
| Fast | 0.3 | Precise, quick answers |
| Deep Research | 0.4–0.5 | Slightly creative for synthesis, report writing |
| Analysis | 0.2–0.3 | Analytical, factual — low hallucination risk |

### 1.6 Implementation

**New method on `Settings`:**
```python
def compute_llm_params(self, model_name: str, mode: str) -> dict:
    """Return optimal params for a model family + mode combination.
    
    Args:
        model_name: e.g. "mistralai/mistral-large-3-675b-instruct"
        mode: "fast" | "analyst" | "deep_research"
    
    Returns:
        {temperature, max_tokens, timeout_seconds, stream_timeout}
    """
    # Step 1: detect model family (substring match, longer patterns first)
    # Step 2: look up mode-specific row
    # Returns dict with all params
```

**Backwards compatibility:**
- Existing callers using hardcoded values continue to work
- New callers (chat.py, report_generator.py, analysis pipeline) use `compute_llm_params()`
- Mode parameter defaults to "fast" for callers that don't specify

---

## 2. Three-Mode Architecture

### 2.1 Fast Mode

**Behavior:** User asks a question → RAG retrieves relevant chunks → LLM streams answer with citations.

- Streaming: yes (real-time answer display)
- Data sources: local RAG documents only
- Token budget: 4K–8K depending on model
- Timeout: streaming, no read timeout
- Citation: inline `📄 filename.pdf (page N)` format

### 2.2 Deep Research Mode

**Behavior:** User asks a complex research question → system searches web + RAG → multi-step synthesis → comprehensive report generated.

**Pipeline:**
1. Query decomposition — break the question into research sub-questions
2. Parallel web search + RAG retrieval (30+ sources typical)
3. Information synthesis — LLM reads all retrieved content, identifies contradictions, fills gaps
4. Report generation — structured report with sections, citations, conclusions

**Web search integration:**
- Brave Search API (`brave_search_api_key` in config)
- Fallback to RAG-only if no web search key configured
- Parallel fetch: web results + RAG chunks combined in context

**Output format:**
```
# Research Report: [Title]

## Executive Summary
[2-3 paragraph overview]

## Key Findings
1. [Finding with source citations]
2. [Finding with source citations]

## Detailed Analysis
[Section-by-section breakdown]

## Sources
- [Web source 1] — URL
- 📄 Legal_Document.pdf (page 5)

## Conclusion
[Summary and recommendations]
```

**Token budget:** 16K–32K (full report can run 10,000+ words)
**Timeout:** 300s cloud, 600s local
**Citations:** Both web URLs and RAG documents

### 2.3 Analysis Mode

**Behavior:** User uploads financial/legal documents (trial balance, ledgers, MOA, company documents) → system processes and analyzes → structured report generated.

**Supported document types:**
- Trial balance (CSV, Excel)
- General ledger (CSV, Excel)
- Company MOA (PDF)
- Financial statements (PDF, Excel)
- Tax filings (PDF)
- Bank statements (PDF)

**Pipeline:**
1. Document ingestion — OCR + parsing (already implemented for PDFs in `document_processor.py`)
2. Data extraction — structured extraction of numbers, dates, clauses
3. Cross-reference analysis — LLM analyzes relationships between documents
4. Compliance checking — compare against UAE laws/regulations in RAG store
5. Report generation — structured financial/legal analysis report

**User interaction:**
- "Upload Documents" panel allows multiple files
- Documents stored temporarily in session context
- User can specify: "Analyze this trial balance against UAE VAT law"
- Progress indicator shows processing stages

**Output format:**
```
# Financial/Legal Analysis Report
## Document(s) Analyzed
- trial_balance_Q1_2026.csv
- company_moa.pdf

## Key Findings
[Findings from document analysis]

## Compliance Check
- VAT compliance: ✅ Compliant / ⚠️ Issues found
- Corporate Tax: ✅ Compliant / ⚠️ Issues found

## Detailed Breakdown
[Section-by-section analysis]

## Recommendations
[Actionable steps based on analysis]
```

**Token budget:** 16K–32K (documents + analysis context can be large)
**Timeout:** 600s cloud, 900s local (document processing + analysis is the slowest mode)
**Citations:** Source document names with extracted sections

---

## 3. RAG Citation System

### 3.1 Problem

When the LLM answers a question using retrieved RAG chunks, it does not cite the source documents. The user has no way to verify which PDF/chunk the answer came from. With NVIDIA API, the model attempts citations but cites the wrong document entirely.

### 3.2 Solution

Two-layer fix:
1. **Metadata enrichment:** RAG `retrieve()` returns chunks with full metadata (filename, page, chunk_id)
2. **Citation enforcement:** System prompt instructs the LLM to cite sources inline; a fallback post-processor inserts source tags if the model doesn't cite

### 3.3 Implementation

**Chunk metadata schema:**
Each retrieved chunk carries:
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
You are a helpful legal/accounting assistant. Your answers must always cite your sources.

When answering, use the following format for each piece of information drawn from the retrieved documents:
📄 [filename] (page N)

Example: "The fee for bounced cheques is AED 50 per incident 📄 Banking_Law_UAE.pdf (page 12)."

If you are unsure about something, say so rather than guessing.
```

**Post-processor fallback:**
If the LLM response contains no citation markers, a post-processing step attaches the top-scoring source chunk's metadata as a footer:
```
Sources consulted:
- 📄 contract_FZ_2024.pdf (page 3) — relevance: 95%
- 📄 invoice_policy.pdf (page 7) — relevance: 82%
```

### 3.4 Mode-specific citation behavior

| Mode | Citation format | Notes |
|---|---|---|
| Fast | Inline `📄 filename.pdf (page N)` | Streamed with answer |
| Deep Research | Inline + footnotes | Both web URLs and RAG sources |
| Analysis | Document names + extracted section | Based on uploaded files |

---

## 4. Per-Key API Key Visibility

### 4.1 Problem

API keys are saved correctly to `.env` via `_update_env_key()`, but after saving they disappear from the Streamlit UI. Users cannot verify whether a key is configured without checking the `.env` file directly.

### 4.2 Solution

Add a visibility flag per API key stored in a separate `settings_keys.json` file (gitignored). The UI respects these flags to display keys as masked, hidden, or not shown.

### 4.3 Implementation

**Settings file:** `backend/api/settings_keys.json` (created if not exists, gitignored)

```json
{
  "NVIDIA_API_KEY": {"visibility": "masked"},
  "ANTHROPIC_API_KEY": {"visibility": "masked"},
  "OPENAI_API_KEY": {"hidden"},
  "MISTRAL_API_KEY": {"hidden"},
  "GROQ_API_KEY": {"hidden"},
  "BRAVE_SEARCH_API_KEY": {"masked"}
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

## 5. Embedding Provider UI with Live Status

### 5.1 Problem

The embedding provider setting (NVIDIA/OpenAI/Ollama) is only configurable via `.env` edit. The current UI shows the provider name and fingerprint but the status (whether it's actually working) is unclear. No way to switch providers from the UI.

### 5.2 Solution

A settings card component showing:
- Current provider with a live status dot
- Dropdown to switch between NVIDIA / OpenAI / Ollama
- Live probe on page load confirms endpoint connectivity
- Switching triggers re-index confirmation if fingerprint changes

### 5.3 Implementation

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

## 6. File Changes Summary

| File | Change |
|---|---|
| `backend/config.py` | Add `compute_llm_params(model_name, mode)` with per-mode, per-family registry |
| `backend/api/chat.py` | Use mode-specific params; inject citation format; add deep research pipeline |
| `backend/api/deep_research.py` | New file: multi-step web search + RAG + synthesis pipeline |
| `backend/api/analysis.py` | New file: document upload, processing, analysis pipeline |
| `backend/core/rag_engine.py` | Ensure all retrievers return full metadata (source_file, page, chunk_id) |
| `backend/core/document_processor.py` | Support trial balance, ledger, MOA parsing for analysis mode |
| `backend/api/settings.py` | Add keys visibility API endpoints |
| `backend/api/settings_keys.json` | New file: per-key visibility flags (gitignored) |
| `frontend/` | Mode selector (Fast/Deep Research/Analysis); embedding card with dropdown + status; eye toggle on API key fields; document upload panel for analysis mode |

---

## 7. Testing Strategy

- Unit tests for `compute_llm_params()` with all model families × all modes
- Integration test: RAG retrieval returns metadata → LLM cites in answer
- API tests: visibility flags save/load correctly
- E2E: switch embedding provider, confirm re-index prompt appears
- E2E: deep research mode — verify multi-step pipeline, web search integration
- E2E: analysis mode — upload trial balance + MOA, verify structured report output
- Verify: with LM Studio in analysis mode, model generates full document analysis with citations

---

## 8. Out of Scope

- Changing the core RAG retrieval algorithm (HybridRetriever / GraphRAG stays as-is)
- Modifying the document chunking strategy
- Supporting additional embedding providers beyond NVIDIA/OpenAI/Ollama
- Non-RAG citation for general conversation
- Real-time document collaboration (multi-user editing)
- Automated report scheduling