# Title Race Condition Fix Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace `asyncio.create_task` with `background_tasks.add_task` for `_generate_title` so the title task always runs after `get_db`'s session has committed, eliminating the race condition that leaves conversations with truncated raw titles.

**Architecture:** FastAPI's `BackgroundTasks` executes registered tasks after the HTTP response is fully sent but still within the ASGI lifecycle, guaranteeing that `get_db`'s `session.commit()` has run before `_generate_title` opens its own `AsyncSessionLocal` session. A 0.1 s defensive delay in `_generate_title` adds extra robustness on slow SQLite I/O. The existing test fixture is updated to use `AsyncMock` so that Starlette's background-task runner (which checks `asyncio.iscoroutinefunction`) properly awaits the mock.

**Tech Stack:** Python 3.12, FastAPI `BackgroundTasks`, SQLAlchemy async, pytest-asyncio, `unittest.mock.AsyncMock`

---

## File Map

| File | Change |
|------|--------|
| `backend/api/chat.py` | Fix two `asyncio.create_task` call-sites; add defensive 0.1 s delay in `_generate_title` |
| `backend/tests/test_chat_title_generation.py` | Add new failing test (TDD); update existing scheduling test to use `AsyncMock` |

---

### Task 1: Write the failing test for background-task scheduling

**Files:**
- Modify: `backend/tests/test_chat_title_generation.py`

- [ ] **Step 1: Write the failing test**

  Add the following test **after** the last existing test (line 154) in `backend/tests/test_chat_title_generation.py`:

  ```python
  @pytest.mark.asyncio
  async def test_title_uses_background_tasks_not_create_task(client):
      """_generate_title must be registered via background_tasks.add_task, not asyncio.create_task.

      BackgroundTasks runs after get_db's session.commit() cleanup, so the
      Conversation row is always visible when _generate_title opens a new session.
      Using asyncio.create_task risks running the coroutine before that commit.
      """
      from fastapi import BackgroundTasks
      from unittest.mock import patch, AsyncMock
      from core.chat.domain_classifier import DomainLabel, ClassifierResult
      from core.llm_manager import LLMResponse

      registered_funcs: list = []
      _orig_add_task = BackgroundTasks.add_task

      def _capture_add_task(self, func, *args, **kwargs):
          registered_funcs.append(func)
          return _orig_add_task(self, func, *args, **kwargs)

      mock_gt = AsyncMock()
      mock_llm = AsyncMock()
      mock_llm.chat = AsyncMock(
          return_value=LLMResponse(content="Answer", tokens_used=5, provider="mock", model="m")
      )

      with (
          patch.object(BackgroundTasks, 'add_task', new=_capture_add_task),
          patch("api.chat._generate_title", new=mock_gt),
          patch("api.chat.classify_domain", new=AsyncMock(
              return_value=ClassifierResult(domain=DomainLabel.VAT, confidence=0.9, alternatives=[])
          )),
          patch("api.chat.get_llm_provider", return_value=mock_llm),
          patch("api.chat.rag_engine.search", new=AsyncMock(return_value=[])),
          patch("api.chat.classify_intent", new=AsyncMock(
              return_value=type("I", (), {"output_type": "answer", "topic": "vat"})()
          )),
      ):
          resp = await client.post("/api/chat/send", json={
              "message": "I have a client who sold a hotel apartment",
              "mode": "fast",
              "stream": False,
          })

      assert resp.status_code == 200
      assert mock_gt in registered_funcs, (
          "_generate_title was not registered via background_tasks.add_task. "
          "Title generation must use background_tasks, not asyncio.create_task. "
          f"Registered funcs: {[getattr(f, '__name__', repr(f)) for f in registered_funcs]}"
      )
  ```

- [ ] **Step 2: Run the new test to verify it fails**

  ```bash
  cd backend
  python -m pytest tests/test_chat_title_generation.py::test_title_uses_background_tasks_not_create_task -v
  ```

  Expected output:
  ```
  FAILED tests/test_chat_title_generation.py::test_title_uses_background_tasks_not_create_task
  AssertionError: _generate_title was not registered via background_tasks.add_task.
  ```

- [ ] **Step 3: Commit the failing test**

  ```bash
  cd backend
  git add tests/test_chat_title_generation.py
  git commit -m "test: add failing test for background_tasks title scheduling

  Verifies that _generate_title is registered via BackgroundTasks.add_task
  rather than asyncio.create_task, as required by the race condition fix.

  Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
  ```

---

### Task 2: Fix the non-streaming path in chat.py

**Files:**
- Modify: `backend/api/chat.py:888-892`

Context: The non-streaming endpoint returns `ChatResponse` directly. `asyncio.create_task` is currently used at line 892. The comment on lines 888–890 explicitly (and incorrectly) stated this is preferred to avoid test interference — after this fix the comment must be updated too.

- [ ] **Step 1: Write the failing state (verify test currently fails)**

  ```bash
  cd backend
  python -m pytest tests/test_chat_title_generation.py::test_title_uses_background_tasks_not_create_task -v
  ```

  Expected: FAIL (confirms the problem exists before fix)

- [ ] **Step 2: Apply the fix to the non-streaming path**

  In `backend/api/chat.py`, locate lines ~888–892 (the block after `await db.commit()`):

  **Before:**
  ```python
      # Schedule after commit so _generate_title can see the committed row.
      # asyncio.create_task (not background_tasks) keeps it out of the ASGI response
      # cycle so it never interferes with test mocks.
      if _title_args:
          asyncio.create_task(_generate_title(*_title_args), name="generate-title")
  ```

  **After:**
  ```python
      # Schedule via BackgroundTasks so it runs after get_db's session.commit()
      # cleanup, guaranteeing the Conversation row is visible when _generate_title
      # opens its own AsyncSessionLocal session.
      if _title_args:
          background_tasks.add_task(_generate_title, *_title_args)
  ```

- [ ] **Step 3: Run the new test to verify it passes**

  ```bash
  cd backend
  python -m pytest tests/test_chat_title_generation.py::test_title_uses_background_tasks_not_create_task -v
  ```

  Expected: PASS

- [ ] **Step 4: Run the full title test file to check for regressions**

  ```bash
  cd backend
  python -m pytest tests/test_chat_title_generation.py -v
  ```

  Expected: `test_title_uses_background_tasks_not_create_task` PASSES; `test_title_scheduled_on_new_conversation` may FAIL (it still uses `MagicMock` — will be fixed in Task 4). The other two unit tests should still PASS.

- [ ] **Step 5: Commit**

  ```bash
  cd backend
  git add api/chat.py
  git commit -m "fix: use background_tasks.add_task for title generation (non-streaming)

  Replaces asyncio.create_task with background_tasks.add_task so the title
  background task always runs after FastAPI/Starlette has completed get_db's
  session.commit() cleanup. This eliminates the race where _generate_title
  opened a new session before the Conversation row was committed.

  Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
  ```

---

### Task 3: Fix the streaming path in chat.py

**Files:**
- Modify: `backend/api/chat.py:673-679`

Context: The streaming path has a `generate()` async generator that yields SSE chunks. `background_tasks` is available in `generate()` via closure over the outer `send_message` scope.

- [ ] **Step 1: Write a failing test for the streaming path**

  Add the following test to `backend/tests/test_chat_title_generation.py` (after the last test):

  ```python
  @pytest.mark.asyncio
  async def test_title_uses_background_tasks_not_create_task_streaming(client):
      """Streaming path must also register _generate_title via background_tasks.add_task."""
      from fastapi import BackgroundTasks
      from unittest.mock import patch, AsyncMock
      from core.chat.domain_classifier import DomainLabel, ClassifierResult
      from core.llm_manager import LLMResponse

      registered_funcs: list = []
      _orig_add_task = BackgroundTasks.add_task

      def _capture_add_task(self, func, *args, **kwargs):
          registered_funcs.append(func)
          return _orig_add_task(self, func, *args, **kwargs)

      mock_gt = AsyncMock()
      mock_llm = AsyncMock()
      mock_llm.chat = AsyncMock(
          return_value=LLMResponse(content="Answer", tokens_used=5, provider="mock", model="m")
      )

      async def _fake_stream(*a, **kw):
          yield "Answer"

      mock_llm.chat_stream = _fake_stream

      with (
          patch.object(BackgroundTasks, 'add_task', new=_capture_add_task),
          patch("api.chat._generate_title", new=mock_gt),
          patch("api.chat.classify_domain", new=AsyncMock(
              return_value=ClassifierResult(domain=DomainLabel.VAT, confidence=0.9, alternatives=[])
          )),
          patch("api.chat.get_llm_provider", return_value=mock_llm),
          patch("api.chat.rag_engine.search", new=AsyncMock(return_value=[])),
          patch("api.chat.classify_intent", new=AsyncMock(
              return_value=type("I", (), {"output_type": "answer", "topic": "vat"})()
          )),
      ):
          resp = await client.post("/api/chat/send", json={
              "message": "I have a client who sold a hotel apartment",
              "mode": "fast",
              "stream": True,
          })

      assert resp.status_code == 200
      assert mock_gt in registered_funcs, (
          "Streaming path: _generate_title was not registered via background_tasks.add_task. "
          f"Registered funcs: {[getattr(f, '__name__', repr(f)) for f in registered_funcs]}"
      )
  ```

- [ ] **Step 2: Run the new streaming test to confirm it fails**

  ```bash
  cd backend
  python -m pytest tests/test_chat_title_generation.py::test_title_uses_background_tasks_not_create_task_streaming -v
  ```

  Expected: FAIL

- [ ] **Step 3: Apply the fix to the streaming path**

  In `backend/api/chat.py`, locate lines ~677–678 inside the `generate()` function (right after `await db.commit()`):

  **Before:**
  ```python
                  if _title_args:
                      asyncio.create_task(_generate_title(*_title_args), name="generate-title")
  ```

  **After:**
  ```python
                  if _title_args:
                      background_tasks.add_task(_generate_title, *_title_args)
  ```

- [ ] **Step 4: Run both new tests to verify they pass**

  ```bash
  cd backend
  python -m pytest tests/test_chat_title_generation.py::test_title_uses_background_tasks_not_create_task tests/test_chat_title_generation.py::test_title_uses_background_tasks_not_create_task_streaming -v
  ```

  Expected: both PASS

- [ ] **Step 5: Commit**

  ```bash
  cd backend
  git add api/chat.py tests/test_chat_title_generation.py
  git commit -m "fix: use background_tasks.add_task for title generation (streaming path)

  Mirrors the non-streaming fix: _generate_title is now registered via
  background_tasks.add_task in the SSE generate() generator as well.
  background_tasks is accessible via closure from the outer send_message scope.

  Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
  ```

---

### Task 4: Add defensive 0.1 s delay to `_generate_title`

**Files:**
- Modify: `backend/api/chat.py:248-269`

Context: The spec recommends a tiny delay for robustness on slow SQLite I/O. Even with `BackgroundTasks`, on very slow disk a 0.1 s pause before opening the session reduces the (already tiny) residual risk.

- [ ] **Step 1: Write a test for the delay behaviour**

  Add to `backend/tests/test_chat_title_generation.py`:

  ```python
  @pytest.mark.asyncio
  async def test_generate_title_has_defensive_delay(title_db):
      """_generate_title must sleep 0.1 s before querying the DB (defensive SQLite robustness)."""
      import asyncio
      from unittest.mock import patch, AsyncMock, call
      from core.llm_manager import LLMResponse

      sleep_calls: list[float] = []
      original_sleep = asyncio.sleep

      async def _capture_sleep(delay):
          sleep_calls.append(delay)
          # Don't actually sleep in tests
          await original_sleep(0)

      with patch("api.chat.AsyncSessionLocal", title_db), \
           patch("asyncio.sleep", side_effect=_capture_sleep), \
           patch("api.chat.get_llm_provider", return_value=AsyncMock(
               chat=AsyncMock(return_value=LLMResponse(
                   content="Test Title", tokens_used=5, provider="mock", model="m"
               ))
           )):
          async with title_db() as db:
              from db.models import Conversation
              conv = Conversation(
                  title="original", llm_provider="mock", llm_model="m", mode="fast"
              )
              db.add(conv)
              await db.flush()
              conv_id = conv.id
              await db.commit()

          from api.chat import _generate_title
          await _generate_title(conv_id, "test message")

      assert 0.1 in sleep_calls, (
          f"_generate_title must call asyncio.sleep(0.1) for defensive delay. "
          f"Observed sleep calls: {sleep_calls}"
      )
  ```

- [ ] **Step 2: Run the new test to verify it fails**

  ```bash
  cd backend
  python -m pytest tests/test_chat_title_generation.py::test_generate_title_has_defensive_delay -v
  ```

  Expected: FAIL with `AssertionError: _generate_title must call asyncio.sleep(0.1)`

- [ ] **Step 3: Add the defensive delay**

  In `backend/api/chat.py`, locate the `_generate_title` function (~lines 248–269):

  **Before:**
  ```python
  async def _generate_title(conversation_id: str, message: str, provider: str | None = None) -> None:
      """Generate a short AI title for a new conversation and persist it. Non-fatal."""
      try:
          llm = get_llm_provider(provider)
  ```

  **After:**
  ```python
  async def _generate_title(conversation_id: str, message: str, provider: str | None = None) -> None:
      """Generate a short AI title for a new conversation and persist it. Non-fatal."""
      await asyncio.sleep(0.1)  # Defensive: let SQLite flush to WAL before opening a new session
      try:
          llm = get_llm_provider(provider)
  ```

- [ ] **Step 4: Run the delay test to verify it passes**

  ```bash
  cd backend
  python -m pytest tests/test_chat_title_generation.py::test_generate_title_has_defensive_delay -v
  ```

  Expected: PASS

- [ ] **Step 5: Run all title tests**

  ```bash
  cd backend
  python -m pytest tests/test_chat_title_generation.py -v
  ```

  Expected: all pass except `test_title_scheduled_on_new_conversation` which will be fixed next.

- [ ] **Step 6: Commit**

  ```bash
  cd backend
  git add api/chat.py tests/test_chat_title_generation.py
  git commit -m "fix: add 0.1s defensive delay to _generate_title for SQLite WAL robustness

  Even with BackgroundTasks, a tiny sleep before opening a new AsyncSessionLocal
  session reduces residual risk on slow SQLite disk I/O per spec recommendation.

  Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
  ```

---

### Task 5: Update `test_title_scheduled_on_new_conversation` to use `AsyncMock`

**Files:**
- Modify: `backend/tests/test_chat_title_generation.py:102-153`

Context: Starlette's BackgroundTask runner checks `asyncio.iscoroutinefunction(func)`. A plain `MagicMock(side_effect=async_fn)` returns `False`, so Starlette calls it via `run_in_threadpool` and the coroutine is never awaited, meaning `title_calls` is never populated. Switching to `AsyncMock` makes the check return `True` and the mock is properly awaited within `client.post(...)`.

- [ ] **Step 1: Verify the existing test currently fails (or is unreliable)**

  ```bash
  cd backend
  python -m pytest tests/test_chat_title_generation.py::test_title_scheduled_on_new_conversation -v
  ```

  With the current `create_task` code it may still pass. After switching to `background_tasks.add_task` in Tasks 2–3, it will fail because `MagicMock` is not awaited by Starlette.

- [ ] **Step 2: Update the test**

  In `backend/tests/test_chat_title_generation.py`, replace the entire `test_title_scheduled_on_new_conversation` function (lines 101–153):

  **Before:**
  ```python
  @pytest.mark.asyncio
  async def test_title_scheduled_on_new_conversation(client):
      """Posting a new message must trigger _generate_title via asyncio.create_task."""
      from api.chat import _generate_title

      title_calls = []

      async def _fake_generate_title(conv_id, message, provider=None):
          title_calls.append(conv_id)

      from unittest.mock import patch as _patch
      from core.chat.domain_classifier import DomainLabel, ClassifierResult
      from core.llm_manager import LLMResponse

      def _stub_cls():
          return ClassifierResult(domain=DomainLabel.VAT, confidence=0.9, alternatives=[])

      mock_llm = AsyncMock()
      mock_llm.chat = AsyncMock(
          return_value=LLMResponse(content="ok", tokens_used=5, provider="mock", model="m")
      )

      async def _stream(*a, **kw):
          yield "ok"

      mock_llm.chat_stream = _stream

      with (
          _patch("api.chat._generate_title", side_effect=_fake_generate_title),
          _patch("api.chat.classify_domain", new=AsyncMock(return_value=_stub_cls())),
          _patch("api.chat.get_llm_provider", return_value=mock_llm),
          _patch("api.chat.rag_engine.search", new=AsyncMock(return_value=[])),
          _patch("api.chat.classify_intent", new=AsyncMock(
              return_value=type("I", (), {"output_type": "answer", "topic": "vat"})()
          )),
      ):
          resp = await client.post("/api/chat/send", json={
              "message": "I have a client who sold a hotel apartment",
              "mode": "fast",
              "stream": False,
          })

      import asyncio as _asyncio
      await _asyncio.sleep(0)  # yield to let create_task'd coroutine run

      assert resp.status_code == 200
      assert len(title_calls) == 1, (
          f"Expected _generate_title to be called once on new conversation, got: {title_calls}"
      )
      conv_id = resp.json().get("conversation_id")
      assert title_calls[0] == conv_id, (
          f"_generate_title called with wrong conv_id: {title_calls[0]} != {conv_id}"
      )
  ```

  **After:**
  ```python
  @pytest.mark.asyncio
  async def test_title_scheduled_on_new_conversation(client):
      """Posting a new message must trigger _generate_title via background_tasks.add_task.

      BackgroundTasks.add_task runs the function within the ASGI lifecycle so it is
      awaited before client.post() returns. AsyncMock is required here so that
      Starlette's runner (which checks asyncio.iscoroutinefunction) properly awaits it.
      """
      title_calls = []

      async def _fake_generate_title(conv_id, message, provider=None):
          title_calls.append(conv_id)

      from unittest.mock import patch as _patch, AsyncMock
      from core.chat.domain_classifier import DomainLabel, ClassifierResult
      from core.llm_manager import LLMResponse

      def _stub_cls():
          return ClassifierResult(domain=DomainLabel.VAT, confidence=0.9, alternatives=[])

      mock_llm = AsyncMock()
      mock_llm.chat = AsyncMock(
          return_value=LLMResponse(content="ok", tokens_used=5, provider="mock", model="m")
      )

      async def _stream(*a, **kw):
          yield "ok"

      mock_llm.chat_stream = _stream

      with (
          _patch("api.chat._generate_title", new=AsyncMock(side_effect=_fake_generate_title)),
          _patch("api.chat.classify_domain", new=AsyncMock(return_value=_stub_cls())),
          _patch("api.chat.get_llm_provider", return_value=mock_llm),
          _patch("api.chat.rag_engine.search", new=AsyncMock(return_value=[])),
          _patch("api.chat.classify_intent", new=AsyncMock(
              return_value=type("I", (), {"output_type": "answer", "topic": "vat"})()
          )),
      ):
          resp = await client.post("/api/chat/send", json={
              "message": "I have a client who sold a hotel apartment",
              "mode": "fast",
              "stream": False,
          })

      # With background_tasks.add_task + AsyncMock, _generate_title is awaited within
      # the ASGI lifecycle, so title_calls is already populated by the time resp returns.
      assert resp.status_code == 200
      assert len(title_calls) == 1, (
          f"Expected _generate_title to be called once on new conversation, got: {title_calls}"
      )
      conv_id = resp.json().get("conversation_id")
      assert title_calls[0] == conv_id, (
          f"_generate_title called with wrong conv_id: {title_calls[0]} != {conv_id}"
      )
  ```

- [ ] **Step 3: Run the updated test**

  ```bash
  cd backend
  python -m pytest tests/test_chat_title_generation.py::test_title_scheduled_on_new_conversation -v
  ```

  Expected: PASS

- [ ] **Step 4: Run all title tests**

  ```bash
  cd backend
  python -m pytest tests/test_chat_title_generation.py -v
  ```

  Expected: all 6 tests PASS

- [ ] **Step 5: Commit**

  ```bash
  cd backend
  git add tests/test_chat_title_generation.py
  git commit -m "test: update title scheduling test to use AsyncMock

  BackgroundTasks.add_task requires the function to be an awaitable (AsyncMock)
  so Starlette's iscoroutinefunction check passes and the mock is properly
  awaited within the ASGI lifecycle. Removes the asyncio.sleep(0) workaround
  that was only needed for create_task.

  Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
  ```

---

### Task 6: Full regression suite

**Files:** None — verify only

- [ ] **Step 1: Run the full backend test suite (non-integration)**

  ```bash
  cd backend
  python -m pytest tests/ -v -m "not integration" --tb=short 2>&1 | tail -40
  ```

  Expected: all previously passing tests still PASS; the 6 title tests all PASS.

- [ ] **Step 2: If any test fails, investigate and fix**

  Common failure modes to check:
  - Any test that patches `api.chat._generate_title` with a plain `MagicMock` and calls the chat endpoint — it needs to switch to `AsyncMock` for the same reason as Task 5.
  - Any test that relies on `asyncio.sleep(0)` to drain title tasks — the sleep is now a no-op (tasks already ran); remove the sleep and verify the assertion still holds.
  - Any test that patches `asyncio.create_task` expecting `name="generate-title"` to appear — that call no longer exists; remove or update those assertions.

- [ ] **Step 3: Final commit (if fixes were needed in Step 2)**

  ```bash
  cd backend
  git add -A
  git commit -m "test: fix remaining tests broken by background_tasks migration

  Any test calling the chat endpoint with a new conversation now needs AsyncMock
  for its _generate_title patch so Starlette's background runner can await it.

  Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
  ```

---

## Self-Review

### Spec Coverage
| Spec Requirement | Task |
|-----------------|------|
| Replace `asyncio.create_task` with `background_tasks.add_task` in non-streaming path | Task 2 |
| Replace `asyncio.create_task` with `background_tasks.add_task` in streaming path | Task 3 |
| `generate()` can access `background_tasks` from outer scope | Task 3 (confirmed in spec — no new code needed) |
| Optional 0.1 s defensive delay in `_generate_title` | Task 4 |
| Reproduction test that confirms the fix | Tasks 1 & 3 |

### Placeholder Scan
No TBDs, TODOs, or incomplete steps. All code blocks contain exact, runnable content.

### Type Consistency
- `_title_args` type is `tuple[str, str, str | None] | None` — used as `background_tasks.add_task(_generate_title, *_title_args)` unpacked, matching `_generate_title(conversation_id: str, message: str, provider: str | None = None)`. ✓
- `BackgroundTasks.add_task` signature: `add_task(func, *args, **kwargs)` — matches all call-sites. ✓
- `AsyncMock(side_effect=async_fn)` — `side_effect` is awaited by AsyncMock, returns the awaited result of `async_fn`. ✓
