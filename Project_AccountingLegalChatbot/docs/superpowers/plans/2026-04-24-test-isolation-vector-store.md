# Test Isolation – Vector Store Fix Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the missing vector store isolation in `conftest.py` so tests never touch the real `vector_store_v2` ChromaDB directory, eliminating the corruption risk and satisfying the SKILL.md spec.

**Architecture:** Set `VECTOR_STORE_DIR` and `UPLOAD_DIR` environment variables to temporary directories at the very top of `conftest.py`, before the app is imported. Because `config.py` reads these values when `Settings()` is first instantiated (at import time), and `rag_engine.py` creates its singleton immediately after, all test-time ChromaDB writes will land in a per-session temp folder that is cleaned up automatically.

**Tech Stack:** Python, pytest, pydantic-settings (BaseSettings), ChromaDB (PersistentClient), tempfile, atexit

---

## Context: The Problem

`backend/tests/conftest.py` mocks the NVIDIA embedding API (via `respx`) but does **not** redirect the ChromaDB vector store. So every test that calls `POST /api/documents/upload` writes real vectors to `backend/vector_store_v2/` on disk.

**Evidence of past corruption:**
- `backend/vector_store_v2_backup_corrupted/` exists — created automatically by `RAGEngine.__init__` when it detects a corrupt store
- `backend/test_output.txt` contains `chromadb.errors.InternalError: mismatched types` from tests run with system Python 3.14 vs the venv's ChromaDB version

**SKILL.md spec requirement (section 3):**
> "When testing RAG logic, prefer mocking `rag_engine` methods or ensure the `VECTOR_STORE_DIR` is set to a temporary directory in the test environment."

---

## File Map

| Action   | File                                        | Responsibility                                  |
|----------|---------------------------------------------|-------------------------------------------------|
| Modify   | `backend/tests/conftest.py:1-18`            | Set env vars before app import + atexit cleanup |
| Verify   | `backend/tests/test_documents.py`           | Upload/delete tests must still pass             |
| Verify   | `backend/tests/test_health.py`              | Stats endpoint test must still pass             |

---

### Task 1: Request a Code Review Before Making Changes

- [ ] **Step 1: Invoke `/superpowers:requesting-code-review` on the current conftest.py and SKILL.md**

  Run this command or invoke the skill in your session:
  ```
  /superpowers:requesting-code-review
  ```
  Provide the reviewer with:
  - `backend/tests/conftest.py` (current state — missing vector store isolation)
  - `docs/superpowers/specs/SKILL.md` (the isolation spec)

  Ask the reviewer specifically:
  1. Is the env-var-before-import approach safe with pydantic-settings v2?
  2. Are there any other places where `rag_engine` or `settings.vector_store_dir` is accessed at module import that we might miss?
  3. Does `UPLOAD_DIR` also need isolation?

- [ ] **Step 2: Confirm or adjust the approach based on review feedback**

  Expected outcome from review: Confirm env vars set before `from main import app` is the correct approach. Note any additional modules to watch.

---

### Task 2: Write the Failing Test to Prove the Problem

**Files:**
- Modify: `backend/tests/test_documents.py`

- [ ] **Step 1: Write a test that asserts isolation (it will PASS with the fix, but documents the requirement)**

  Add this test to the end of `backend/tests/test_documents.py`:

  ```python
  import os
  from pathlib import Path
  
  @pytest.mark.asyncio
  async def test_vector_store_uses_temp_dir_not_real_store(client):
      """Vector store must NOT point at the real vector_store_v2 directory during tests."""
      from config import settings
      from pathlib import Path
      real_store = Path(__file__).parent.parent / "vector_store_v2"
      test_store = Path(settings.vector_store_dir)
      assert test_store != real_store.resolve(), (
          f"Tests are writing to the REAL vector store at {real_store}! "
          "This violates the isolation spec (docs/superpowers/specs/SKILL.md). "
          "Fix: set VECTOR_STORE_DIR env var to a temp dir in conftest.py before app import."
      )
  ```

- [ ] **Step 2: Run the test to confirm it FAILS before the fix**

  ```powershell
  cd "backend"
  .\venv\Scripts\python.exe -m pytest tests/test_documents.py::test_vector_store_uses_temp_dir_not_real_store -v
  ```

  Expected output:
  ```
  FAILED tests/test_documents.py::test_vector_store_uses_temp_dir_not_real_store
  AssertionError: Tests are writing to the REAL vector store at ...
  ```

---

### Task 3: Fix `conftest.py` — Isolate Vector Store and Upload Dir

**Files:**
- Modify: `backend/tests/conftest.py:1-18`

- [ ] **Step 1: Replace the top of conftest.py with the isolated version**

  Replace everything from line 1 through the `sys.path.insert` line with:

  ```python
  """
  Pytest fixtures shared across all backend tests.
  """
  import asyncio
  import atexit
  import os
  import shutil
  import sys
  import tempfile
  from pathlib import Path

  import pytest
  import pytest_asyncio
  from httpx import AsyncClient, ASGITransport
  from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

  # Ensure backend/ is importable
  sys.path.insert(0, str(Path(__file__).parent.parent))

  # ── Vector store + upload isolation ───────────────────────────────
  # MUST be set before any app import so that config.Settings() and
  # the rag_engine singleton both pick up the temp directories.
  _TEST_VECTOR_STORE_DIR = tempfile.mkdtemp(prefix="pytest_vector_store_")
  _TEST_UPLOAD_DIR = tempfile.mkdtemp(prefix="pytest_uploads_")
  os.environ["VECTOR_STORE_DIR"] = _TEST_VECTOR_STORE_DIR
  os.environ["UPLOAD_DIR"] = _TEST_UPLOAD_DIR

  def _cleanup_test_dirs():
      shutil.rmtree(_TEST_VECTOR_STORE_DIR, ignore_errors=True)
      shutil.rmtree(_TEST_UPLOAD_DIR, ignore_errors=True)

  atexit.register(_cleanup_test_dirs)
  # ──────────────────────────────────────────────────────────────────

  from main import app
  from db.database import Base, get_db
  ```

  The rest of conftest.py (all fixtures from `TEST_DB_URL` onward) stays **exactly as-is**.

- [ ] **Step 2: Run the new isolation test to confirm it now PASSES**

  ```powershell
  .\venv\Scripts\python.exe -m pytest tests/test_documents.py::test_vector_store_uses_temp_dir_not_real_store -v
  ```

  Expected output:
  ```
  PASSED tests/test_documents.py::test_vector_store_uses_temp_dir_not_real_store
  ```

---

### Task 4: Verify All 412+ Tests Still Pass

**Files:**
- No changes — run existing test suite

- [ ] **Step 1: Run the full test suite with the venv Python**

  ```powershell
  cd "backend"
  .\venv\Scripts\python.exe -m pytest --tb=short -q
  ```

  Expected output:
  ```
  413 passed, 2 skipped in XX.XXs
  ```

  > **If any tests fail:** Check if they import `settings.vector_store_dir` or `settings.upload_dir` at module-level before conftest.py runs. If so, patch those directly in the affected test.

- [ ] **Step 2: Confirm the temp dirs are cleaned up after the session**

  After the test run completes, verify the temp dirs are gone:

  ```powershell
  Get-ChildItem $env:TEMP -Filter "pytest_vector_store_*" -ErrorAction SilentlyContinue
  Get-ChildItem $env:TEMP -Filter "pytest_uploads_*" -ErrorAction SilentlyContinue
  ```

  Expected: No directories listed (atexit cleanup ran).

---

### Task 5: Invoke Code Review on the Changes

- [ ] **Step 1: Stage the changes**

  ```powershell
  git add backend/tests/conftest.py backend/tests/test_documents.py
  ```

- [ ] **Step 2: Invoke `/superpowers:requesting-code-review`**

  ```
  /superpowers:requesting-code-review
  ```

  Provide the diff of the staged changes. Ask the reviewer to check:
  1. Does the env-var override actually take effect before `Settings()` reads it?
  2. Could `atexit` cleanup fail silently without the test knowing?
  3. Is the new isolation test assertion message clear enough?

- [ ] **Step 3: Address any blocking issues found in the review**

  If the reviewer finds issues (e.g., import order problem), resolve them before committing.

---

### Task 6: Commit

- [ ] **Step 1: Commit the fix**

  ```powershell
  git add backend/tests/conftest.py backend/tests/test_documents.py
  git commit -m "fix(tests): isolate vector store and upload dir in conftest per SKILL.md spec

  - Set VECTOR_STORE_DIR and UPLOAD_DIR env vars to temp dirs before
    app import so rag_engine singleton and settings never touch the
    real vector_store_v2 directory during tests.
  - Add test_vector_store_uses_temp_dir_not_real_store to guard regression.
  - Root cause: tests were writing to real ChromaDB, causing corruption
    (evidenced by vector_store_v2_backup_corrupted directory).
  
  Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
  ```

---

## Self-Review Checklist

**Spec coverage:**
- [x] SKILL.md §3 "Isolated Vector Store" — Task 3 sets VECTOR_STORE_DIR to temp dir ✓
- [x] SKILL.md §3 "UPLOAD_DIR" — also isolated for completeness ✓
- [x] SKILL.md "Verification: 410+ tests pass" — Task 4 confirms this ✓
- [x] Requesting code review before and after — Tasks 1 + 5 ✓

**Placeholder scan:** No TBDs or "implement later" found — all steps have concrete code.

**Type consistency:** No types introduced. Method names (`tempfile.mkdtemp`, `shutil.rmtree`, `atexit.register`) are standard library — consistent throughout.
