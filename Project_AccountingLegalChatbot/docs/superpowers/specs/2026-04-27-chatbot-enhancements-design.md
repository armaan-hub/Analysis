# Design: AccountingLegalChatbot Enhancements
**Date:** 2026-04-27  
**Status:** Approved  
**Source:** Ported from `25. 21-Mar-2026` UAE AI Assistant + new source display design

---

## Problem

The current chatbot is missing several quality and automation features proven in the previous UAE AI Assistant project. Specifically:
- No anti-hallucination guard — LLM is called even when the knowledge base has no matching chunks
- No citation validation — fabricated quotes or claims go undetected
- Domain classifier keyword fallback uses exact-match only — typos cause wrong domain routing
- Search relies solely on ChromaDB vector search — no keyword fallback when vector scores are weak
- Documents must be uploaded manually — no auto-ingestion from government law sources
- Source display shows only file name + page — no relevance score, excerpt, or domain tag

---

## Architecture: Option B — Dedicated Modules

All new logic lives in focused new files under `backend/core/`. Existing files receive minimal, surgical wiring changes. Each module is independently testable.

### New Files

```
backend/core/accuracy/
  __init__.py
  citation_validator.py       # validate_citations() + no-LLM guard

backend/core/search/
  __init__.py
  hybrid_engine.py            # vector + keyword always-on merge

backend/core/pipeline/
  __init__.py
  fta_scraper.py              # nightly UAE law scraper
  auto_sync.py                # watchdog: PDF drop → auto-ingest
```

### Modified Files

| File | Change |
|------|--------|
| `backend/core/rag_engine.py` | Replace direct ChromaDB search call with `HybridEngine.search()` |
| `backend/api/chat.py` | Add no-LLM guard + `validate_citations()` call after LLM response |
| `backend/core/chat/domain_classifier.py` | Add `difflib` fuzzy matching to keyword fallback |
| `backend/main.py` | Register APScheduler nightly job + watchdog observer on startup |
| `frontend/src/components/` | Add `SourcePanel.tsx` — rich expandable source cards |

---

## Feature 1: No-LLM Guard

**Location:** `backend/api/chat.py` — before LLM invocation in all chat modes  
**Trigger:** RAG engine returns 0 chunks after search  
**Action:** Return `"I don't have this in my documents."` immediately without calling the LLM API  
**Applies to:** Fast mode, Deep Research mode, Council mode (all paths)  
**Benefit:** Eliminates hallucination when the knowledge base has no relevant content; saves API cost

```python
# Pseudocode — applied in chat.py before LLM call
if not rag_chunks:
    return ChatResponse(answer="I don't have this in my documents.", sources=[])
```

---

## Feature 2: Citation Validator

**Location:** `backend/core/accuracy/citation_validator.py`  
**Trigger:** After LLM returns answer, before sending response to client  
**Logic:**
1. Skip validation if answer contains "I don't have" (honest refusal — nothing to validate)
2. Extract all quoted text (between `"` or `"` `"`) from the answer
3. Check each quote against combined source chunk text — if fewer than 2 of the first 5 words appear in any source, flag as fabricated
4. Detect suspicious claim patterns: `"the law states: <long unquoted text>"`, `"according to Article X: <long unquoted text>"`
5. If **2 or more** fabrications detected: append 🚨 warning block at end of answer
6. If fewer than 2: return answer unchanged

**Warning format:**
```
🚨 CRITICAL LEGAL ACCURACY WARNING:
Found N potential issues:
• X unverified quote(s)
• Y unverified claim(s)
Please verify with official documents before using for compliance.
```

---

## Feature 3: Fuzzy Domain Matching

**Location:** `backend/core/chat/domain_classifier.py` — keyword fallback path  
**Current behaviour:** Exact string match against domain keyword lists  
**New behaviour:** After exact-match fails, run `difflib.get_close_matches(word, domain_keywords, n=1, cutoff=0.78)` on each word in the query  
**Configurable:** `FUZZY_CUTOFF` env var (default `0.78`)  
**Examples:** `"vatt"` → `"vat"` → VAT domain; `"corparate"` → `"corporate"` → corporate_tax domain  
**Confidence:** Fuzzy match returns same confidence as keyword match (0.8) but only triggers when LLM classifier fails

---

## Feature 4: Hybrid Search Engine

**Location:** `backend/core/search/hybrid_engine.py`  
**Mode:** Always-on — runs both searches for every query  

### Pipeline

```
Query
  ├─ ChromaDB vector search  →  results with cosine similarity scores (0–1)
  └─ Keyword search          →  results with fuzz.token_set_ratio scores (0–100, normalised to 0–1)
         ↓
  Merge by (file, page_or_chunk_id)
    - Duplicate: keep higher score
    - Unique: keep as-is
         ↓
  Sort by merged score descending
         ↓
  Apply domain filter (existing logic, unchanged)
         ↓
  Return top_k results
```

### Keyword Search Scoring (3 signals)
1. **Exact phrase match:** score = 1.0 if full query found in chunk text
2. **Keyword presence:** score = (matching_keywords / total_keywords) × 0.8
3. **Fuzzy match:** `fuzz.token_set_ratio(query, chunk[:200]) / 100 × 0.7`
4. Combined = `max(signal_1, signal_2, signal_3)`

### Score Normalisation
- Vector search: ChromaDB returns cosine similarity (already 0–1); use as-is
- Keyword search: divide raw score by 100 before merge

---

## Feature 5: FTA Scraper

**Location:** `backend/core/pipeline/fta_scraper.py`  
**Schedule:** APScheduler cron job, midnight daily (`0 0 * * *`), registered in `backend/main.py` lifespan  
**Targets:**
- `https://tax.gov.ae/en/Legislation.aspx`
- `https://www.moec.gov.ae/en/laws`
- `https://www.moet.gov.ae/en/laws`

**Deduplication:** MD5 hash of PDF binary content — stored in `backend/data/scraped_hashes.txt`; skips files already seen  
**On new PDF found:**
1. Download to temp file
2. Infer category (`law` or `finance`) from filename using domain classifier keywords
3. Call existing document ingest pipeline (`ingest_document()`) directly
4. Log success/failure to backend logger

**Error handling:** Any single URL failure is caught and logged — does not stop processing remaining URLs

---

## Feature 6: Auto-Sync Watchdog

**Location:** `backend/core/pipeline/auto_sync.py`  
**Library:** `watchdog`  
**Watches:** `data_source_law/` and `data_source_finance/` directories  
**Trigger:** `on_created` or `on_moved` event for `.pdf` files  
**Debounce:** 10 seconds — prevents triggering multiple builds when batch-dropping files  
**On trigger:**
1. Wait 2 seconds for OS to finish writing the file
2. Infer category from directory name (`law` or `finance`)
3. Call existing document ingest pipeline
4. Log result

**Lifecycle:** Observer started in `backend/main.py` lifespan startup, stopped on shutdown

---

## Feature 7: Source Display — Option C (Rich Expandable)

**Location:** `frontend/src/components/SourcePanel.tsx` (new)  
**Data available:** RAGEngine already returns `score`, `excerpt` (first 200 chars of chunk text), and `domain` per source — no backend changes needed  

### Visual Specification

```
📚 SOURCES (N found)
┌─────────────────────────────────────────────────────┐
│ UAE_VAT_Law_2017.pdf   Pg 12  [95%] [VAT]      ▾   │  ← auto-expanded
│ "…hotel apartments shall be treated as residential   │
│  for VAT purposes only where the period of stay      │
│  exceeds 6 months under Article 45(3)…"             │
├─────────────────────────────────────────────────────┤
│ FTA_Guide_Real_Estate.pdf  Pg 4  [78%] [VAT]   ▸   │  ← collapsed
└─────────────────────────────────────────────────────┘
```

### Score Colour Coding
- ≥ 80%: green badge
- 60–79%: orange badge
- < 60%: grey badge

### Behaviour
- First (highest-score) source: auto-expanded on render
- Remaining sources: collapsed, expand on click
- Domain tag: sourced from chunk `domain` metadata field
- `chat_history_viewer.py`: update to render excerpt + score in console output

---

## Feature 8: Full Chunk Text in LLM Prompt (Verification)

**Location:** `backend/core/rag_engine.py` → `build_augmented_prompt()`  
**Action:** Verify that the augmented prompt includes raw chunk text (up to 700 chars per chunk), not just file names. If not already present, add text inclusion.  
**Format:**
```
[[SOURCE: filename.pdf, page N]]
<chunk text up to 700 chars>
```

---

## Testing Strategy

Each feature gets its own test file following existing pytest conventions (`asyncio_mode=auto`, `httpx.AsyncClient` with `ASGITransport`, in-memory SQLite):

| Feature | Test File |
|---------|-----------|
| No-LLM guard | `tests/test_no_llm_guard.py` |
| Citation validator | `tests/test_citation_validator.py` |
| Fuzzy domain matching | `tests/test_fuzzy_domain.py` |
| Hybrid search | `tests/test_hybrid_engine.py` |
| FTA scraper | `tests/test_fta_scraper.py` |
| Auto-sync | `tests/test_auto_sync.py` |
| Source display (API contract) | `tests/test_source_display.py` |

All tests must pass before the feature is considered done. Full suite (`pytest backend/`) must remain green after every feature.

---

## Implementation Phases

### Phase 1 — Accuracy Layer (independent, highest value)
1. `citation_validator.py` + tests
2. No-LLM guard in `chat.py` + tests
3. Fuzzy domain matching in `domain_classifier.py` + tests

### Phase 2 — Search Layer (depends on Phase 1 being stable)
4. `hybrid_engine.py` + tests
5. Wire `HybridEngine` into `rag_engine.py`
6. Verify full chunk text in `build_augmented_prompt()`

### Phase 3 — Data Pipeline (independent of Phases 1–2)
7. `fta_scraper.py` + tests
8. `auto_sync.py` + tests
9. Register both in `main.py` lifespan

### Phase 4 — Frontend Source Display
10. `SourcePanel.tsx` component + tests
11. Wire into chat message renderer
12. Update `chat_history_viewer.py`

---

## Definition of Done

- All 7 new test files pass
- Full backend suite (`pytest backend/`) passes — 0 failures
- Frontend builds without errors (`npm run build`)
- `chat_history_viewer.py` shows score + excerpt in output
- No regressions in existing VAT/hotel apartment scenario tests
