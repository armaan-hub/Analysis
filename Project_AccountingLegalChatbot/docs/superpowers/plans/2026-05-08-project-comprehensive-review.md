# Comprehensive Project Review and Fix Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Complete audit of the Accounting & Legal AI Chatbot project to identify and fix all issues, run all tests, and verify everything works correctly.

**Architecture:** Python FastAPI backend with SQLite database, React + Vite frontend, RAG-powered document analysis, hybrid vector-graph retrieval system.

**Tech Stack:** Python 3.11+, FastAPI, SQLAlchemy, SQLite, React, TypeScript, Vite, ChromaDB, HNSW.

---

## Issues Identified

### 1. Database Path Configuration
- **File:** `backend/config.py:67`
- **Issue:** `database_url` uses relative path `sqlite:///./data/chatbot.db` which resolves incorrectly when running from project root
- **Fix:** Change to absolute path using `Path(__file__).parent`

### 2. OneDrive Path References
- **Files:** Multiple files contain hardcoded Windows OneDrive paths
- **Issue:** Paths reference `C:\Users\Armaan\OneDrive - The Era Corporations` or macOS OneDrive path
- **Fix:** Replace with relative paths or `Path.home()` references

### 3. Empty Database Created
- **File:** `backend/data/chatbot.db`
- **Issue:** Database file was empty (0 bytes) with no tables
- **Fix:** Reinitialize database with proper schema

### 4. Chat History Viewer Fix
- **File:** `chat_history_viewer.py`
- **Issue:** Script failed due to empty database
- **Fix:** Database path configuration corrected

---

## Task List

### Task 0: Create LLM Model Specifications (COMPLETED)

**Files Created:**
- `docs/superpowers/llm-models/fast-mode-model.md` - Fast Mode complete specification
- `docs/superpowers/llm-models/deep-research-mode-model.md` - Deep Research Mode complete specification
- `docs/superpowers/llm-models/analyst-mode-model.md` - Analyst Mode complete specification
- `docs/superpowers/llm-models/llm-models-overview.md` - Comprehensive overview

**Summary:**
All three LLM mode specifications have been created with complete details for Fast, Deep Research, and Analyst modes including:
- Model configurations for all providers (NVIDIA, OpenAI, Claude, Mistral, Groq, Ollama)
- Temperature settings, token budgets, top-K values
- Use cases and performance characteristics
- Implementation notes and configuration examples
- Testing checklists

---

### Task 1: Fix Database URL Configuration

**Note:** Git hooks are working correctly. Pre-commit validates changes and post-commit auto-pushes for commits with keywords: feature/fix/major/update/improvement/refactor/security/hotfix.

**Files:**
- Modify: `backend/config.py:67`

- [ ] **Step 1: Change database_url to use absolute path**

```python
# Old (line 67):
database_url: str = "sqlite:///./data/chatbot.db"

# New:
database_url: str = f"sqlite:///{Path(__file__).parent}/data/chatbot.db"
```

- [ ] **Step 2: Verify the change**

Run: `python -c "import sys; sys.path.insert(0, 'backend'); from config import settings; print(settings.database_url)"`
Expected: `/absolute/path/to/backend/data/chatbot.db`

- [ ] **Step 3: Commit**

```bash
git add backend/config.py
git commit -m "fix: use absolute path for database_url"
```

---

### Task 2: Remove OneDrive Path References

**Files:**
- Modify: `backend/bulk_ingest.py` (lines with Windows OneDrive paths)
- Modify: `backend/tests/test_*.py` (test fixture paths)
- Modify: `docs/superpowers/plans/*.md` (documentation paths)
- Modify: `run_project.ps1` (comment only - informational)

- [ ] **Step 1: Fix bulk_ingest.py Windows paths**

```python
# Old:
r"C:\Users\Armaan\OneDrive - The Era Corporations\Study\Armaan"

# New:
str(Path.home() / "Library" / "CloudStorage" / "GoogleDrive-armaanmishra86@gmail.com" / "My Drive" / "Study" / "Armaan")
```

- [ ] **Step 2: Fix test fixture paths**

Replace all `r"C:\Users\Armaan\OneDrive - The Era Corporations"` with relative paths or `Path.cwd()` references.

- [ ] **Step 3: Update documentation paths**

Replace hardcoded OneDrive paths with relative paths or `Path(__file__).parent` references.

- [ ] **Step 4: Commit**

```bash
git add backend/bulk_ingest.py backend/tests/*.py docs/superpowers/plans/*.md
git commit -m "fix: remove hardcoded OneDrive paths"
```

---

### Task 3: Verify Database Initialization

**Files:**
- Verify: `backend/data/chatbot.db` exists with tables
- Verify: `backend/db/models.py` defines all required tables

- [ ] **Step 1: Check database has tables**

Run: `python -c "import sqlite3; conn = sqlite3.connect('backend/data/chatbot.db'); cursor = conn.cursor(); cursor.execute(\"SELECT name FROM sqlite_master WHERE type='table'\"); print(cursor.fetchall())"`
Expected: `['conversations', 'messages', 'documents', ...]`

- [ ] **Step 2: Run backend to verify it starts correctly**

Run: `cd backend && python main.py`
Expected: Server starts on http://localhost:8001 with logs showing database initialized

- [ ] **Step 3: Test chat endpoint**

Run: `curl -X POST http://localhost:8001/api/chat/send_message -H "Content-Type: application/json" -d '{"message":"test","conversation_id":"test-id"}'`
Expected: 200 OK with response

- [ ] **Step 4: Commit any changes**

```bash
git add backend/data/chatbot.db
git commit -m "fix: ensure database initializes correctly"
```

---

### Task 4: Run All Backend Tests

**Files:**
- Test: `backend/tests/` (all test files)

- [ ] **Step 1: Run API tests**

Run: `cd backend && pytest tests/api/ -v`
Expected: All tests pass

- [ ] **Step 2: Run core tests**

Run: `cd backend && pytest tests/core/ -v`
Expected: All tests pass

- [ ] **Step 3: Run db tests**

Run: `cd backend && pytest tests/db/ -v`
Expected: All tests pass

- [ ] **Step 4: Fix any failing tests**

For each failing test:
1. Read the test to understand expected behavior
2. Read the implementation to find the bug
3. Fix the bug
4. Re-run the test to verify fix

- [ ] **Step 5: Commit fixes**

```bash
git add backend/tests/*.py backend/**/*.py
git commit -m "fix: resolve test failures"
```

---

### Task 5: Verify Chat History Viewer Works

**Files:**
- Verify: `chat_history_viewer.py`
- Verify: `backend/data/chatbot.db`

- [ ] **Step 1: Run chat_history_viewer with --list**

Run: `python chat_history_viewer.py --list`
Expected: Lists recent conversations with colors

- [ ] **Step 2: Run chat_history_viewer with --stats**

Run: `python chat_history_viewer.py --stats`
Expected: Shows database statistics

- [ ] **Step 3: Run chat_history_viewer with --search**

Run: `python chat_history_viewer.py --search "test"`
Expected: Shows matching conversations

- [ ] **Step 4: Run chat_history_viewer with --export**

Run: `python chat_history_viewer.py --export`
Expected: Exports to `chat_history_export.json`

- [ ] **Step 5: Verify interactive mode**

Run: `python chat_history_viewer.py`
Expected: Interactive menu displays correctly

---

### Task 6: Verify Frontend Startup

**Files:**
- Verify: `frontend/package.json`
- Verify: `frontend/src/App.tsx`

- [ ] **Step 1: Check frontend dependencies**

Run: `cd frontend && npm install`
Expected: All dependencies installed

- [ ] **Step 2: Run frontend dev server**

Run: `cd frontend && npm run dev`
Expected: Server starts on http://localhost:5173

- [ ] **Step 3: Verify chat interface loads**

Open http://localhost:5173 in browser
Expected: Chat interface displays correctly

---

### Task 7: Final Verification

**Files:**
- All modified files

- [ ] **Step 1: Run full test suite**

Run: `cd backend && pytest tests/ -v`
Expected: All tests pass

- [ ] **Step 2: Verify backend health endpoint**

Run: `curl http://localhost:8001/health`
Expected: `{"status":"ok"}`

- [ ] **Step 3: Verify frontend health**

Open http://localhost:5173
Expected: Frontend loads without errors

- [ ] **Step 4: Commit all changes**

```bash
git add -A
git commit -m "fix: comprehensive project review and fixes"
```

- [ ] **Step 5: Push to remote**

Run: `git push origin main`
Expected: Push succeeds

---

## Self-Review Checklist

After completing all tasks:

1. **Database:** All tables exist and are accessible
2. **Tests:** All backend tests pass
3. **Backend:** Server starts and responds correctly
4. **Frontend:** Dev server starts and UI loads
5. **Chat History Viewer:** All commands work
6. **No OneDrive paths:** No hardcoded paths remain
7. **Documentation:** All docs updated with correct paths

---

## Execution Choice

**Plan complete. Two execution options:**

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task using `superpowers:subagent-driven-development`, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using `superpowers:executing-plans`, batch execution with checkpoints

**Which approach?**
