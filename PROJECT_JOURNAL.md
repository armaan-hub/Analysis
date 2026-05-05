# Project Journal — Accounting & Legal AI Chatbot

> **Repository:** [armaan-hub/Analysis](https://github.com/armaan-hub/Analysis.git)  
> **Branches:** `main` (production), `v2` (hybrid RAG), `deep-research` (research mode)  
> **Backend URL:** http://localhost:8002  
> **Frontend URL:** http://localhost:5173 (run `npm run dev` in `frontend/`)

---

## ⚙️ Workflow Rules (ALWAYS ENFORCED)

### Rule 1 — Planning & Brainstorming
> Whenever any planning, brainstorming, or design decision is made, **add a summary entry** to this file under the relevant milestone section AND in the Chronological Log at the bottom.

### Rule 2 — Push on Every Update
> Whenever any **major or minor update** is made to this project (code fix, test, config, this journal), **push to GitHub immediately**:
> ```bash
> git add -A
> git commit -m "docs/feat/fix: <description>\n\nCo-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
> git push origin <branch>   # branch decided at push time
> ```
> This journal file itself must be committed and pushed every time it is updated.

---

## 📦 Project Overview

**What it is:** A RAG-powered AI chatbot for UAE Accounting & Legal queries. Answers questions about VAT, e-invoicing, corporate tax, IFRS, labour law, and commercial law using internal document knowledge bases.

**Architecture:**
- **Hybrid RAG** = ChromaDB vector search + Graph RAG entity traversal + BM25 keyword re-ranking
- **Council Mode** = multi-expert critique pipeline (CA, CPA, CMA, Analyst personas)
- **Deep Research** = query decomposition → web search → RAG synthesis → structured report
- **LLM:** NVIDIA NIM — `mistral-large-3-675b` (deep analysis) + `devstral-2-123b` (fast mode)
- **Backend:** FastAPI, Python 3.11, `~/chatbot_venv`
- **Frontend:** React 18 / TypeScript / Vite
- **Data stores:** ChromaDB 0.5.15 (vector), SQLite (graph entities), SQLite (chat history)

**Environment:**
```bash
# Always use venv — system Python is incompatible with ChromaDB 0.5.15
~/chatbot_venv/bin/python3
source ~/chatbot_venv/bin/activate

# Project paths
~/chatbot_local/Project_AccountingLegalChatbot/   # avoid OneDrive path (slow imports)
VECTOR_STORE_DIR=/Users/armaan/vector_store_v2
GRAPH_STORE_DIR=/Users/armaan/graph_store

# Rebuild graph after any graph_rag.py change
~/chatbot_venv/bin/python3 ~/rebuild_graph.py
```

---

## 🏁 Milestones

### Milestone 1 — Project Recovery (Laptop Loss)
*After losing the development laptop, the full project was recovered and verified from two sources: local OneDrive sync and GitHub.*

| Date | Decision | Outcome |
|------|----------|---------|
| 2026-05-04 | Compared OneDrive local files vs `armaan-hub/Analysis` GitHub repo | Local already had all 3 branches merged — no data lost |
| 2026-05-04 | Chose GitHub `main` as authoritative source going forward | Clean working tree, local changes committed and pushed |

**Branches merged into local project at time of recovery:**
- `main` — core chatbot, vector RAG, council, deep research
- `v2` — hybrid RAG (Graph RAG + keyword re-ranking layer)
- `deep-research` — query decomposer, web search integration, research synthesis

---

### Milestone 2 — Full Audit & Bug Fixes
*Full TDD audit of the codebase. Three bugs found and fixed.*

#### Bug 1: E-Invoicing Graph Score = 0
- **Root cause:** `_FINANCE_TERMS` in `graph_rag.py` was missing all e-invoicing domain terms
- **Fix:** Added 15 terms: `e-invoicing`, `e-invoice`, `invoicing`, `invoice`, `electronic invoice`, `peppol`, `fta`, `federal tax authority`, `tax invoice`, `credit note`, `debit note`, `clearance`, `reporting model`, `vat return`, `vat-return`
- **Tests:** `TestEInvoicingTerms` class in `test_entity_extraction_uae.py` (6 specific assertions)
- **Graph rebuild:** 111,854 entities after rebuild
- **Commit:** `cf5815f`

#### Bug 2: Hybrid Retriever Score Corruption
- **Root cause:** `blend_results()` in `hybrid_retriever.py` overwrote `score` field with `combined_score`. The broad fallback in `chat.py` reads `score` expecting raw vector score — it was getting the blended score instead, so the fallback switch condition was always wrong.
- **Fix:** Saved `r["vector_score"] = r["score"]` before blend; restored `b["score"] = b["vector_score"]` after blend
- **Commit:** `6fcc83f`

#### Bug 3: Flaky Web Ingestion Test
- **Root cause:** Test patched only `_hybrid_retriever.retrieve` but the broad fallback path calls `rag_engine.search()` directly — bypassing the mock. Fire-and-forget `asyncio.create_task()` also completed before test assertions.
- **Fix:** Patch both `api.chat._hybrid_retriever.retrieve` AND `api.chat.rag_engine.search`; add two `await asyncio.sleep(0)` yields after stream consumption
- **Commit:** `16e1aca`

**Final test result:** `632 passed, 0 failed, 8 skipped`

---

### Milestone 3 — Live E2E Verification
*Live verification of all major endpoints after fixes.*

| Test | Result | Notes |
|------|--------|-------|
| Health check `/api/health` | ✅ `{"status":"ok"}` | — |
| E-Invoicing query | ✅ 15 sources returned, FTA/Peppol content present | No 404 URLs generated |
| Council mode | ✅ CA, CPA, CMA, Analyst + synthesis fired | Full SSE stream |
| Corporate tax RAG | ✅ Scores up to 0.96 | High quality retrieval |
| Pre-existing ChromaDB HNSW | ⚠️ Warning logged, falls back to BM25 | Not introduced by our changes |

**Pre-existing known issue (NOT blocking):**  
ChromaDB HNSW error: `"Cannot return results in contiguous 2D array. Probably ef or M is too small"` → falls back to BM25 keyword search. Requires re-ingesting documents with tuned HNSW params.

---

### Milestone 4 — Developer Skill & Documentation
*Knowledge base skill file created for future AI agents working on this codebase.*

- **Skill file created:** `skills/accounting-legal-chatbot-rag.md`
- **Contents:** Architecture overview, environment setup, critical code patterns, common bugs & fixes, testing guide, API reference, data stores
- **This journal created:** `PROJECT_JOURNAL.md` (you are reading it) — enforces Rule 1 & Rule 2

---

## 📋 Chronological Session Log

### 2026-05-04 — Full Audit, Recovery & All Fixes

**Goal:** Recover project after laptop loss. Compare OneDrive vs GitHub. Fix all known issues. Verify live E2E.

**Context:** User lost development laptop. Local OneDrive path had the project but state unknown. GitHub `armaan-hub/Analysis` had 3 branches (main, v2, deep-research).

**Decisions made:**
1. Local project already had all 3 branches merged — no recovery needed from Git
2. GitHub `main` branch designated as authoritative
3. TDD approach: write failing tests first, then fix code
4. Used `~/chatbot_local/` clone to avoid OneDrive 20s+ import delays

**Changes made:**
- `backend/core/rag/graph_rag.py` — Added 15 e-invoicing terms to `_FINANCE_TERMS`
- `backend/core/rag/hybrid_retriever.py` — Preserve vector score before blend, restore after
- `backend/tests/test_entity_extraction_uae.py` — Tightened `TestEInvoicingTerms` to specific assertions
- `backend/tests/api/test_chat_web_ingestion.py` — Dual mock patch + asyncio yield fix
- `skills/accounting-legal-chatbot-rag.md` — Created developer knowledge base skill
- `PROJECT_JOURNAL.md` — Created this file

**Commits pushed to `origin/main`:**
- `cf5815f` — feat(graph): add e-invoicing/peppol/fta terms + TDD tests
- `6fcc83f` — fix(retriever): preserve vector score before blend_results
- `16e1aca` — fix(tests): tighten TestEInvoicingTerms + fix flaky web ingestion test

**Outcome:** 632 tests passing (0 failing), all E2E endpoints verified, skill file created, all commits pushed.

---

*Append new sessions below this line. Each entry: date, goal, decisions, changes, commits, outcome.*

---
