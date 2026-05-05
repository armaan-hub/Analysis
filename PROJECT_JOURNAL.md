# Project Journal — Accounting & Legal AI Chatbot

> **Repository:** [armaan-hub/Analysis](https://github.com/armaan-hub/Analysis.git)  
> **Branches:** `main` (production), `v2` (hybrid RAG), `deep-research` (research mode)  
> **Backend URL:** http://localhost:8002  
> **Frontend URL:** http://localhost:5173 (run `npm run dev` in `frontend/`)

---

### Session: 2026-05-05 — Folder Cleanup & Archive

**Goal:** Reduce OneDrive `35. 11-Apr-2026 Agentic AI` folder from ~6GB to ~850MB by archiving redundant files.

**What was archived (into `archive_backup_2026-05-05.zip`, 2.5GB):**
- `Project_AccountingLegalChatbot/` (3.1GB) — canonical copy is in git at `~/chatbot_local`
- `25. 21-Mar-2026/` (1.4GB) — superseded March 2026 session
- `desktop/` (576MB) — orphaned `node_modules`, no source code
- `frontend/` (269MB) — stale standalone frontend + `node_modules`
- `backend/`, `vector_store/`, `vector_store_v2/`, `src/` — stale root-level duplicates
- Log files (`frontend_server.log`, `backend_server.log`, `run_project.log`)
- Caches/temp: `.pytest_cache/`, `.vs/`, `.claude/`, `.code-review-graph/`, `conv_id.txt`

**What was kept:**
- `Main Branch/` — working project snapshot
- `data_source_finance/` (403MB) + `data_source_law/` (124MB) — irreplaceable RAG documents
- `PROJECT_JOURNAL.md`, `.env`, `skills/`, `brain/`, `Gemini_Sessions/`, `Testing data/`
- Setup scripts, git infrastructure, `docs/`

**Result:** Folder reduced from ~6GB to ~850MB. ZIP backup at `archive_backup_2026-05-05.zip`.

**Tools used:** Brainstorming skill → Writing Plans skill → Subagent-Driven Development (GPT-5.3-Codex + Claude Opus 4.7)

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

## 📚 Quick Links

| Resource | Path / URL |
|----------|-----------|
| Full Project README | `Project_AccountingLegalChatbot/README.md` |
| Developer Guide | `Project_AccountingLegalChatbot/DEVELOPER_GUIDE.md` |
| Swagger UI (live) | http://localhost:8002/docs |
| Health Check | http://localhost:8002/api/health |
| Frontend | http://localhost:5173 |
| Skills / AI Knowledge Base | `skills/accounting-legal-chatbot-rag.md` |
| Design Specs | `Project_AccountingLegalChatbot/docs/superpowers/specs/` |

---

## 🚀 Quick Start (macOS)

### Prerequisites
- Python 3.11+, Node.js 20+
- `.env` file in `Project_AccountingLegalChatbot/backend/` (see below)

### 1. Clone & set up venv
```bash
git clone https://github.com/armaan-hub/Analysis.git ~/chatbot_local
cd ~/chatbot_local/Project_AccountingLegalChatbot/backend
python3.11 -m venv ~/chatbot_venv
source ~/chatbot_venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure `.env`
```bash
cp backend/.env.example backend/.env
# Edit backend/.env — minimum required keys:
```
```env
LLM_PROVIDER=nvidia
NVIDIA_API_KEY=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   # deep/main model
NVIDIA_FAST_API_KEY=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   # fast mode
VECTOR_STORE_DIR=./vector_store_v2
DATABASE_URL=sqlite:///./data/chatbot.db
```

### 3. Start backend
```bash
cd ~/chatbot_local/Project_AccountingLegalChatbot/backend
source ~/chatbot_venv/bin/activate
uvicorn main:app --host 0.0.0.0 --port 8002 --reload
```

### 4. Start frontend
```bash
cd ~/chatbot_local/Project_AccountingLegalChatbot/frontend
npm install   # first time only
npm run dev   # → http://localhost:5173
```

> ⚠️ **Important:** Always use `~/chatbot_venv/bin/python3` — system Python ships with ChromaDB 1.5.8 which is incompatible. Venv has 0.5.15.

---

## 🌿 Branch Strategy

| Branch | Purpose | Status |
|--------|---------|--------|
| `main` | Production — all 3 branches merged here | ✅ Authoritative |
| `v2` | Hybrid RAG experiments (Graph RAG + BM25) | Merged into main |
| `deep-research` | Query decomposition + web search synthesis | Merged into main |

**All active development happens on `main`.** Feature branches cut from `main`, PR back to `main`.

---

## 📂 Data Sources

Documents placed in these watched directories are **auto-ingested** at backend startup and on file change:

```
backend/data_source_finance/   ← Finance docs: IFRS standards, UAE VAT, Corporate Tax, FTA guidance
backend/data_source_law/       ← Legal docs: UAE Commercial Law, Labour Law, Regulatory updates
```

**Supported formats:** PDF (text + scanned OCR), DOCX, XLSX  
**Domain tagging:** filenames determine domain filter applied during RAG search  
**Manual upload:** via web UI or `POST /api/documents/upload`

After adding new documents, restart the backend — ingestion runs automatically on startup.

---

## 🔌 API Reference

Backend base URL: **http://localhost:8002**  
Interactive docs: **http://localhost:8002/docs**

### Chat
| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/chat/send` | Send message; `stream=true` for SSE |
| `GET` | `/api/chat/conversations` | List all conversations |
| `GET` | `/api/chat/conversations/{id}` | Get conversation + messages |
| `DELETE` | `/api/chat/conversations/{id}` | Delete conversation |

### Documents
| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/documents/upload` | Upload & index PDF/Word/Excel |
| `GET` | `/api/documents/` | List indexed documents |
| `DELETE` | `/api/documents/{id}` | Remove from index |

### Reports
| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/reports/generate/ifrs` | IFRS financial statement |
| `POST` | `/api/reports/generate/vat` | UAE VAT return |
| `POST` | `/api/reports/generate/corptax` | Corporate tax filing |

### Settings / Health
| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/health` | `{"status":"ok"}` |
| `GET` | `/api/settings/current` | Current LLM config |
| `POST` | `/api/settings/providers/switch` | Switch LLM provider |

### Chat Modes
| Mode | Description |
|------|-------------|
| `fast` | Quick lookups — devstral-2-123b, higher top-k |
| `deep` | Research synthesis — mistral-large-3-675b, query decomposition |
| `council` | 4-expert panel (CA / CPA / CMA / Analyst) + synthesis |
| `analyst` | Financial analyst persona |

---

## 🧪 Testing Guide

```bash
cd ~/chatbot_local/Project_AccountingLegalChatbot/backend
source ~/chatbot_venv/bin/activate

# Run all unit tests (no LLM keys needed)
pytest tests/ -m "not integration" -q

# With coverage
pytest tests/ -m "not integration" --cov=. --cov-report=term-missing

# Integration tests (requires live NVIDIA keys in .env)
RUN_LLM_TESTS=1 pytest tests/ -m integration -v
```

**Current status (as of 2026-05-04):** `632 passed, 0 failed, 8 skipped`

**Critical test files:**
| Test File | What it tests |
|-----------|--------------|
| `tests/test_entity_extraction_uae.py` | Graph RAG entity extraction + e-invoicing terms |
| `tests/api/test_chat_web_ingestion.py` | Web search auto-ingest + broad fallback logic |
| `tests/test_hybrid_retriever.py` | Score preservation through blend_results |
| `tests/api/test_chat.py` | Core chat API, RAG grounding, streaming |

**After any `graph_rag.py` change** — must rebuild the graph:
```bash
~/chatbot_venv/bin/python3 ~/rebuild_graph.py   # ~2-3 min, produces ~111K entities
```

---

## ⚠️ Known Issues

| Issue | Severity | Status | Notes |
|-------|----------|--------|-------|
| ChromaDB HNSW `ef or M too small` error | Medium | Pre-existing, not blocking | Falls back to BM25 keyword search. Fix: re-ingest all docs with tuned HNSW params (`ef=100`, `M=16`) |
| `_FINANCE_TERMS` / `_LEGAL_TERMS` must never overlap | — | Guard in place | `graph_rag.py` lines 50-52 raise `ValueError` at import if overlap found |
| OneDrive path import delay | Low | Workaround in place | Use `~/chatbot_local/` clone, not OneDrive path |
| Local Agentic AI `.git` corrupted object | Low | Known | Use `~/chatbot_local` for all git operations |

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

### Milestone 5 — UI & Response Integrity Hardening
*Reliability and UX improvements completed for chat output and citation safety.*

- ✅ **Full-Width Chat Layout:** AI chat bubbles now render full available column width (user bubbles unchanged at max 75%).
- ✅ **URL Hallucination Guard:** Markdown hyperlinks are now stripped when no allowed URLs exist, preventing fabricated URL links in Fast/RAG mode.

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

### 2026-05-05 — PROJECT_JOURNAL.md Completion & Review

**Goal:** Verify PROJECT_JOURNAL.md covers entire project details; add all missing sections.

**Gaps identified:**
- Missing Quick Links to README, Swagger, DEVELOPER_GUIDE
- No macOS Quick Start (README had Windows-only)
- No Branch Strategy guide (main/v2/deep-research usage)
- No Data Sources setup (data_source_finance / data_source_law)
- No API endpoint reference in journal
- No test execution commands
- Known Issues not consolidated in one place

**Changes made:**
- `PROJECT_JOURNAL.md` — Added 7 new sections: Quick Links, Quick Start (macOS), Branch Strategy, Data Sources, API Reference, Testing Guide, Known Issues

**Commits pushed to `origin/main`:**
- `0d7b684` — docs: add PROJECT_JOURNAL.md (initial version)
- Next commit: this completion update

**Outcome:** Journal now covers full project onboarding + operational reference.

---

### 2026-05-05 — Frontend Startup Fix (Full Stack Verified)

**Goal:** Get frontend running reliably at http://localhost:5173, connected to backend at http://localhost:8002.

**Root causes identified:**
1. Backend was running on system Python 3.14 with ChromaDB **1.5.8** (incompatible) instead of venv ChromaDB 0.5.15
2. `node_modules` was empty in `chatbot_local` clone — `npm install` never ran after git clone
3. No `frontend/.env` file — `api-config.ts` defaulted to port 8001, backend runs on 8002
4. No macOS startup script (Windows `run_project.ps1` existed but not usable on Mac)

**Decisions made:**
1. Tasks dispatched as 3 parallel subagents (GPT-5.3-Codex Wave 1) + 2 parallel (Wave 2)
2. E2E verified with Claude Opus 4.7 — noted that RAG sources for e-invoicing query pull from RAKEZ business lists (pre-existing data gap, not a code bug)
3. `frontend/.env` is gitignored — must be created locally on every new clone

**Changes made:**
- Backend restarted with `~/chatbot_venv/bin/python3` (ChromaDB 0.5.15) on port 8002
- `npm install` run in `frontend/` → 340 modules, Vite 8.0.8
- `frontend/.env` created locally: `VITE_API_BASE_URL=http://localhost:8002`
- `frontend/.env.example` updated: port corrected from 8000 → 8002
- `run_project.sh` created: macOS launcher for both backend + frontend

**E2E test results (2026-05-05):**
- Health: ✅ `{"status":"ok"}`
- E-Invoicing query: ✅ 15 sources, Peppol/FTA mentioned in response, streaming SSE working
- CORS: ✅ `access-control-allow-origin: *`
- Frontend: ✅ HTTP 200, title `Legal & Accounting AI Studio`, 8 assets

**Known data gap (pre-existing):** RAG retrieval for e-invoicing returns RAKEZ business activity lists (scores 0.28–0.51) rather than dedicated e-invoicing documents. LLM generates correct answer from its own knowledge. Fix: ingest FTA e-invoicing PDF documents into `data_source_finance/`.

**Commits pushed to `origin/main`:**
- `d423c0b` — fix(frontend): correct VITE_API_BASE_URL default port to 8002
- `e300181` — feat(scripts): add macOS run_project.sh launcher

**Outcome:** Both services running — http://localhost:8002 (backend) + http://localhost:5173 (frontend). Full stack E2E verified.

---

### Session: 2026-05-05 — Chat Layout, URL Hallucination Guard, Missing Dependencies

**Goals:** Fix AI chat responses capped at 720px, eliminate LLM URL hallucination in Fast/RAG mode, install 4 missing frontend packages, create living DEPENDENCIES.md.

**Completed:**

#### T1 — Chat Layout Full-Width (commits b519954, 581f049)
- Removed `max-width: 720px` from `.chat-msg` → `width: 100%`
- Added `flex: 1; min-width: 0` to `.chat-msg__body` so AI bubble width resolves against flex parent
- Added `width: 100%` to `.chat-msg--ai .chat-msg__bubble`
- AI messages now fill full available column width; user bubbles keep `max-width: 75%`
- 3 CSS regression tests added

#### T2 — URL Hallucination Guard (commits 3b43842, e77070b, f7aa48c)
- `citation_validator.py`: when `allowed_urls` is empty, strips ALL markdown hyperlinks (was returning text unchanged — the root cause of hallucinated URLs passing through)
- Both branches now use robust regex: `(?<!!)\[([^\]]+)\]\((https?://(?:[^\s()]+|\([^\s()]*\))+)\)` — handles parens-in-URL (e.g., `Tax_(UAE)`), preserves image links
- `chat.py`: removed `if _sources:` guards from streaming AND non-streaming paths — strip always runs
- `prompt_router.py`: added `URL_NO_HALLUCINATE_RULE` constant, appended to all 10 domain prompts
- 9 tests

#### T3 — Missing npm Packages (commit d8d2095)
- Installed: `remark-math`, `rehype-katex`, `rehype-highlight`, `react-syntax-highlighter`, `@types/react-syntax-highlighter`
- 4 import tests confirming packages load correctly

#### T4 — DEPENDENCIES.md (commit 4e0a2ed)
- Created `DEPENDENCIES.md` at repo root with 41 backend Python deps + 35 frontend npm deps
- Update rule: "Whenever a new library is added to requirements.txt or package.json, this file MUST be updated and committed in the same PR/commit"

**Also fixed (prior session, carried forward):**
- `normalizeMarkdown.ts` missing utility created from test spec (12 tests)
- `.gitignore` fixed: `lib/` → `/lib/` (was silently ignoring `frontend/src/lib/`)

*Append new sessions below this line. Each entry: date, goal, decisions, changes, commits, outcome.*

---
