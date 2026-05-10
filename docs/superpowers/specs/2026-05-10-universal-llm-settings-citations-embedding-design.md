# Universal LLM Settings, RAG Citations, API Key Visibility & Embedding Status

**Date:** 2026-05-10
**Status:** Approved
**Type:** Feature design

---

## Overview

The system operates in **three distinct modes**, each with different token budgets, timeout requirements, data sources, and response patterns.

| Mode | Use case | Data sources | Response type | Max tokens (cloud) | Max tokens (local) | Timeout (cloud) | Timeout (local) |
|---|---|---|---|---|---|---|---|
| **Fast** | Quick Q&A | RAG (local docs) | Streaming answer | 4096–8192 | 8192 | Streaming | Streaming |
| **Deep Research** | Comprehensive research | Web + RAG | Full report/thesis | 32768 | 32768 | 300s | 600s |
| **Analysis** | Document-heavy analysis | User uploads + RAG | Structured report | 32768 | 32768 | 600s | 900s |

---

## 1. Universal Adaptive LLM Settings

### 1.1 Per-Mode, Per-Family Token Budgets

`compute_llm_params(model_name, mode)` returns optimal params:

| Model family | Fast max tokens | Deep/Analysis max tokens | Fast timeout | Deep/Analysis timeout |
|---|---|---|---|---|
| `claude` | 8192 | 32768 | 90s | 300s/600s |
| `gpt-4` | 8192 | 32768 | 90s | 300s/600s |
| `gpt-3.5` | 4096 | 8192 | 30s | 60s/90s |
| `ollama` | 8192 | 32768 | 180s | 300s/600s |
| `lmstudio` | 8192 | 32768 | 300s | 600s/900s |
| `mistral` | 8192 | 32768 | 90s | 300s/600s |
| `groq` | 8192 | 16384 | 45s | 180s/300s |
| `nvidia` | 8192 | 32768 | 90s | 300s/600s |
| `default` | 4096 | 16384 | 60s | 180s/300s |

### 1.2 Per-Mode Temperature

| Mode | Temperature | Reasoning |
|---|---|---|
| Fast | 0.3 | Precise, quick answers |
| Deep Research | 0.4 | Slightly creative for synthesis |
| Analysis | 0.2–0.3 | Analytical, factual |

### 1.3 Mode-Specific Retrieval Budget

| Mode | top_k | Over-fetch multiplier | Rationale |
|---|---|---|---|
| Fast | 8 | 2× | Quick relevant context |
| Deep Research | 20 | 2.5× | More sources for synthesis |
| Analysis | 16 | 2× | Balance between breadth and noise |

### 1.4 Streaming Behavior

- **Fast**: streaming (no read timeout on local, 10s connect on cloud)
- **Deep Research**: non-streaming (full response for report)
- **Analysis**: non-streaming (full response for structured report)

---

## 2. Three-Mode Architecture

### 2.1 Fast Mode

- Streaming LLM response
- Data source: RAG (local documents via ChromaDB)
- Citation: inline `📄 filename.pdf (page N)`
- Token budget: family-specific (4K–8K)
- Context management: sliding window, 12K token conversation cap

### 2.2 Deep Research Mode — Hybrid Pipeline

**Auto-detection:** The system analyzes the user's query complexity before deciding the path.

**Detection criteria (complex = multi-step):**
- Query contains: "compare", "analyze", "evaluate", "comprehensive", "full report", "thesis"
- Or query exceeds 200 characters and mentions specific legal frameworks
- Or query references multiple jurisdictions or law numbers

**Simple path (single LLM call):**
1. RAG retrieval (top_k=20)
2. Web search (Brave Search) in parallel — up to 10 results
3. Combined context injected into single LLM call
4. Full report generated in one response

**Complex path (multi-step pipeline):**
1. **Query decomposition** — LLM breaks question into 3-6 research sub-questions
2. **Parallel retrieval** — for each sub-question: RAG retrieval + web search simultaneously
3. **Synthesis passes** — LLM reads all results, identifies gaps, resolves contradictions
4. **Gap-filling** — follow-up searches for unresolved topics
5. **Report generation** — structured output (executive summary, findings, sources, conclusion)

**Citation:** Both web URLs and RAG document citations in footnote format.

**Output format:**
```markdown
# Research Report: [Title]

## Executive Summary
[2-3 paragraph overview]

## Key Findings
1. [Finding with citation]
2. [Finding with citation]

## Detailed Analysis
[Section-by-section]

## Sources
- [Web source] — URL
- 📄 Legal_Document.pdf (page 5)

## Conclusion
[Summary and recommendations]
```

### 2.3 Analysis Mode

**Document types supported:**
- Trial balance (CSV, Excel)
- General ledger (CSV, Excel)
- Company MOA (PDF)
- Financial statements (PDF, Excel)
- Tax filings (PDF)
- Bank statements (PDF)

**Scalability fix for large files:**
- CSV/Excel with >5,000 rows: processed in batches of 2,000 rows, metadata preserved per batch
- Batch extraction results joined with `---BATCH_N---` separator for chunking
- Row count, column names, and date range extracted as structured metadata

**Pipeline:**
1. **Document ingestion** — OCR + parsing (PDF via PyMuPDF + Tesseract; Excel/CSV via openpyxl streaming)
2. **Data extraction** — structured extraction: account names, amounts, dates, clause text
3. **Context enrichment** — retrieved relevant UAE law/regulation chunks from RAG
4. **Cross-reference analysis** — LLM analyzes relationships between documents and laws
5. **Compliance checking** — compare extracted data against VAT/Corporate Tax/IFRS rules in RAG
6. **Report generation** — structured financial/legal analysis

**Context window management:**
- Conversation context: 12K token sliding window
- Retrieved chunks: max 32 chunks (16K context budget for chunks in 32K total)
- User documents: pre-processed and chunked; top 8 most relevant document sections selected
- System prompt: compressed to essential instructions

**Output format:**
```markdown
# Financial/Legal Analysis Report

## Document(s) Analyzed
- trial_balance_Q1_2026.csv (3,847 rows)
- company_moa.pdf

## Key Findings
[Findings from document analysis]

## Compliance Check
| Check | Result | Details |
|---|---|---|
| VAT compliance | ✅ Compliant | ... |
| Corporate Tax | ⚠️ Issues found | ... |

## Detailed Breakdown
[Section-by-section]

## Sources
- 📄 trial_balance_Q1_2026.csv (row 1-200)
- 📄 Banking_Law_UAE.pdf (page 8)

## Recommendations
[Actionable steps]
```

### 2.4 Large-Scale Document Handling (Future-Proofing)

**For when the system grows to thousands of documents:**

| Threshold | Strategy |
|---|---|
| 0–2,000 chunks | Single ChromaDB collection, local HNSW (current setup) |
| 2,000–10,000 chunks | ChromaDB persistent client, HNSW auto-tuning |
| 10,000–50,000 chunks | ChromaDB server mode (client connects to remote Chroma) |
| 50,000+ chunks | pgvector migration (PostgreSQL + pgvector extension) |

**The code must not hardcode ChromaDB-local assumptions.** The `RAGEngine` class must remain the abstraction layer so the underlying store can be swapped without changing call sites.

---

## 3. RAG Citation System

### 3.1 Chunk Metadata Schema

All retrievers (HybridRetriever, GraphRAG) return:
```python
{
    "text": "...",               # chunk text
    "chunk_id": "uuid",          # unique chunk identifier
    "source_file": "contract.pdf", # original filename
    "page": 3,                   # page number
    "score": 0.95,               # relevance score
    "document_id": "...",        # internal document ID
    "section": "Article 4"       # section heading (if available)
}
```

### 3.2 Citation Enforcement

**System prompt injection:**
```
You are a helpful legal/accounting assistant. Your answers must always cite your sources.

When answering, use the following format for each piece of information drawn from the retrieved documents:
📄 [filename] (page N)

Example: "The fee for bounced cheques is AED 50 per incident 📄 Banking_Law_UAE.pdf (page 12)."

If you are unsure about something, say so rather than guessing.
```

### 3.3 Post-Processor Fallback

If LLM response has no citation markers:
```
Sources consulted:
- 📄 contract_FZ_2024.pdf (page 3) — relevance: 95%
- 📄 invoice_policy.pdf (page 7) — relevance: 82%
```

### 3.4 Mode-Specific Citation Formats

| Mode | Format | Notes |
|---|---|---|
| Fast | Inline `📄 filename.pdf (page N)` | Streamed with answer |
| Deep Research | Inline + footnotes | Both web URLs and RAG sources |
| Analysis | Document name + row/page + section | Based on uploaded files |

---

## 4. Per-Key API Key Visibility

### 4.1 Settings File

`backend/api/settings_keys.json` (gitignored):
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

### 4.2 Visibility Levels

- `masked`: `•••••••••` + green "Configured" badge
- `hidden`: green "Configured" badge only
- `none`: not displayed at all

### 4.3 UI

- Eye icon (👁) toggle per key field, cycles: hidden → masked → none → hidden
- Default for new keys: `masked`

### 4.4 API

- `GET /api/settings/keys` — returns visibility config (no key values)
- `PUT /api/settings/keys/{key_name}` — update visibility for a specific key
- API keys still write to `.env` as before; visibility flags write to `settings_keys.json`

---

## 5. Embedding Provider UI with Live Status

### 5.1 Provider Card

```
┌─────────────────────────────────────────┐
│ Embedding Provider                      │
│ [Nvidia ▼]  🟢 Connected                │
│ Model: nvidia/nv-embed-qa               │
│ Dimension: 1024 | Chunks: 1,247          │
└─────────────────────────────────────────┘
```

### 5.2 Status Dot

- 🟢 Green: responds within 5s
- 🟡 Yellow: responds within 5-15s
- 🔴 Red: no response / error

### 5.3 Switch Behavior

- Dropdown to switch between NVIDIA / OpenAI / Ollama
- Switching to a provider with different fingerprint → re-index confirmation prompt
- Re-index triggers background job with progress indicator

### 5.4 API Endpoints

- `GET /api/settings/embedding-status` — provider, model, status, document count
- `POST /api/settings/embedding-switch` — switch provider, trigger re-index if needed

---

## 6. File Changes Summary

| File | Change |
|---|---|
| `backend/config.py` | Add `compute_llm_params(model_name, mode)` with per-mode, per-family registry |
| `backend/api/chat.py` | Use mode-specific params; citation injection; hybrid deep research detection |
| `backend/api/deep_research.py` | New file: hybrid pipeline (simple = single call, complex = multi-step with decomposition, parallel retrieval, synthesis passes, gap-filling, report) |
| `backend/api/analysis.py` | New file: batch CSV/Excel processing, document upload, multi-stage analysis pipeline, context budgeting |
| `backend/core/rag_engine.py` | Ensure all retrievers return full metadata; add mode-specific top_k parameter |
| `backend/core/document_processor.py` | Add batch processing for large CSV/Excel (>5,000 rows); structured metadata extraction for financial documents |
| `backend/api/settings.py` | Add keys visibility API endpoints |
| `backend/api/settings_keys.json` | New file: per-key visibility flags (gitignored) |
| `frontend/` | Mode selector (Fast/Deep Research/Analysis); embedding card with dropdown + status; eye toggle on API key fields; document upload panel for analysis mode |

---

## 7. Out of Scope

- Changing the core RAG retrieval algorithm (HybridRetriever / GraphRAG stays as-is)
- ChromaDB server mode or pgvector migration (future scalability enhancement)
- Real-time multi-user document collaboration
- Automated report scheduling
- Supporting additional embedding providers beyond NVIDIA/OpenAI/Ollama