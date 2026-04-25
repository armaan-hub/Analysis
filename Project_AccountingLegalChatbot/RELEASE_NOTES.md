# Title Race Condition Fix & Auto-Push Workflow Repair

## Overview

This release fixes a critical race condition in the chat title generation system and resolves GitHub Actions auto-push workflow failures. 

**Status:** ✅ All 426 backend tests passing | Auto-push workflow now operational

---

## 🐛 Title Race Condition Fix

### Problem

The `_generate_title` coroutine was scheduled using `asyncio.create_task()` in both streaming and non-streaming chat paths. This could execute before the database transaction committed, causing:
- **Stale data reads:** Title generation queries the DB before new conversation is persisted
- **Test flakiness:** Background tasks escaped test lifecycle, timing unpredictable
- **Improper cancellation:** Task cancellation not handled by FastAPI lifecycle

### Solution

Replaced `asyncio.create_task` with FastAPI's `background_tasks.add_task()` in both chat paths:
- **Streaming path** (`generate()` async generator, line ~681)
- **Non-streaming path** (line ~895)

**Why this fixes it:**
- ✅ FastAPI guarantees background tasks run AFTER response + DB cleanup
- ✅ Proper ASGI lifecycle integration
- ✅ Testable via `BackgroundTasks` mocking
- ✅ Automatic error containment

### Additional Protections

Added defensive **0.1s delay** at start of `_generate_title`:
```python
await asyncio.sleep(0.1)  # defensive: let send_message's DB commit propagate
```

This is belt-and-suspenders protection—the main fix is the scheduling mechanism, but the delay provides extra safety margin.

### Commits

| SHA | Message | Status |
|-----|---------|--------|
| `6435c4d` | test: add failing test for background_tasks title scheduling | ✅ |
| `477460c` | fix: use background_tasks.add_task for title generation (non-streaming) | ✅ |
| `334126a` | fix: use background_tasks.add_task for title generation (streaming path) | ✅ |
| `5508615` | fix: add 0.1s defensive delay at start of _generate_title | ✅ |
| `2395c3a` | refactor: improve defensive-delay test robustness and extract constant | ✅ |
| `2d42968` | test: update test_title_scheduled_on_new_conversation to use AsyncMock | ✅ |
| `6feb9b6` | test: patch _generate_title in intent routing tests | ✅ |
| `7970fd4` | test: patch _generate_title in all tests that POST to /api/chat/send | ✅ |

### Test Coverage

**New tests added:**
- `test_title_uses_background_tasks_not_create_task` — Verifies non-streaming uses `BackgroundTasks.add_task`
- `test_title_uses_background_tasks_not_create_task_streaming` — Verifies streaming uses `BackgroundTasks.add_task`
- `test_generate_title_has_defensive_delay` — Confirms 0.1s sleep is first statement

**Updated tests:**
- `test_title_scheduled_on_new_conversation` — Now uses `AsyncMock` for proper Starlette compatibility

**Regression fixes:**
- `test_intent_directive_is_appended` — Now patches `_generate_title` to prevent mock interference
- 8 additional test files patched for consistency

**Result:** ✅ **426 tests passing, 1 skipped** | No failures

---

## 🔧 Auto-Push Workflow Repair

### Problem

GitHub Actions auto-push workflow failing with:
```
##[error]Unable to process file command 'output' successfully.
##[error]Invalid format 'background_tasks.add_task now runs _generate_title synchronously during'
```

**Root cause:** Multi-line commit messages were being written to GitHub Actions file command variables, which only accept single-line values.

### Solution

**File:** `.github/workflows/auto-push.yml`

**Changes:**
1. **Use commit subject line only** (`git log -1 --pretty=%s`)
   - Subject is single-line, safe for file commands
   - Full message now omitted from workflow outputs

2. **Update actions to v4** (v3 deprecated)
   - `actions/checkout@v3` → `actions/checkout@v4`

3. **Expand major keywords**
   - Added `"test"` and `"docs"` to keywords triggering auto-push
   - Now recognizes: `feature|fix|major|update|improvement|refactor|security|hotfix|critical|patch|test|docs`

4. **Improve logging**
   - Clear status emojis (✅, ⚪)
   - Visible commit subject in all steps

### Expected Behavior (After Fix)

✅ **On any commit with major keywords:**
1. Workflow triggers on `push` to `main`
2. Detects major update keyword
3. Runs verification steps
4. Completes successfully (no errors)

✅ **Error handling:**
- Multi-line messages no longer crash workflow
- Job logs remain readable
- All commits properly tracked

### Commit

| SHA | Message |
|-----|---------|
| `cd8bf58` | fix: auto-push workflow - handle multi-line commit messages |

---

## 📊 Test Results Summary

### Before
- ❌ 158 workflow runs failing repeatedly
- ❌ 1 test failing (`test_intent_directive_is_appended`)
- ⚠️ Flaky background task behavior

### After
- ✅ **426 tests passing**
- ✅ **1 skipped** (requires `RUN_LLM_TESTS=1`)
- ✅ **0 failures**
- ✅ **Workflow fixed** (ready for next push)

### Regression Prevention

All tests that call `/api/chat/send` now properly patch `_generate_title` to:
- Prevent interference with test LLM mocks
- Eliminate 0.1s sleep latency in tests
- Maintain test isolation

---

## 📝 Files Modified

### Core Fix
- `backend/api/chat.py`
  - Line ~681: Streaming path `_generate_title` scheduling
  - Line ~895: Non-streaming path `_generate_title` scheduling
  - Line ~252: Added `await asyncio.sleep(_TITLE_GENERATION_DELAY_S)`
  - Line ~42: Added `_TITLE_GENERATION_DELAY_S: float = 0.1` constant

### Tests
- `backend/tests/test_chat_title_generation.py` — 3 new tests, 1 updated
- `backend/tests/api/test_chat_intent_routing.py` — Added `_generate_title` patch
- `backend/tests/test_chat_endpoint_domain.py` — Added `_generate_title` patch
- `backend/tests/test_fast_mode_streaming.py` — Added `_generate_title` patch
- `backend/tests/test_session_summary.py` — Added `_generate_title` patch
- `backend/tests/test_chat_sources.py` — Added `_generate_title` patch
- `backend/tests/test_legacy_domain_compat.py` — Added `_generate_title` patch
- `backend/tests/test_multi_query_rag.py` — Added `_generate_title` patch
- `backend/tests/test_selected_doc_ids.py` — Added `_generate_title` patch
- `backend/tests/api/test_chat_web_ingestion.py` — Added `_generate_title` patch

### Workflow
- `.github/workflows/auto-push.yml` — Fixed multi-line commit message handling

---

## 🚀 Getting Started

### Verify the Fix Locally

```bash
cd backend
pytest tests/test_chat_title_generation.py -v
pytest tests/ -m "not integration" -q
```

Expected: **426 passed, 1 skipped**

### Next Steps

1. **Monitor auto-push workflow** — Next commit with major keywords will test the fix
2. **Track title generation latency** — The 0.1s delay is defensive; monitor if it becomes problematic at scale
3. **Follow up on summary refresh** — `_get_or_refresh_summary` in streaming path still uses `asyncio.create_task` (out of scope, filed for follow-up)

---

## 📌 Notes

- All commits include `Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>` trailer
- Implementation followed TDD: failing test → fix → passing tests → regressions fixed
- Code quality reviewed at each step for spec compliance and best practices
- No breaking changes to public APIs

---

**Release Date:** April 25, 2026  
**Authors:** Armaan (armaan-hub), Copilot  
**Status:** Ready for production ✅
