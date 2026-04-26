# Two-Model Mode Routing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Route Fast mode chat to `mistral-small-4-119b-2603` (with `reasoning_effort="medium"`) and keep Analyst / Deep Research / Council on `mistral-large-3-675b-instruct-2512` (unlimited tokens, no reasoning_effort).

**Architecture:** A `mode` parameter is added to `get_llm_provider()` — when the active provider is NVIDIA and `mode == "fast"`, it returns a provider instance built with `settings.nvidia_fast_model`. The `_build_payload` method gains an optional `reasoning_effort` parameter injected into the NVIDIA API payload when set. Both chat endpoints in `chat.py` are updated to pass the mode and reasoning effort from the request.

**Tech Stack:** Python 3.11, FastAPI, httpx, pydantic-settings, pytest, NVIDIA NIM (OpenAI-compatible REST API)

---

## File Map

| File | Action | Responsibility |
|------|--------|----------------|
| `.env` | Modify | Update API key + add `NVIDIA_FAST_MODEL` |
| `.env.example` | Modify | Document the new `NVIDIA_FAST_MODEL` variable |
| `backend/config.py` | Modify | Add `nvidia_fast_model`, `nvidia_fast_reasoning_effort`; update `fast_max_tokens`, `temperature` |
| `backend/core/llm_manager.py` | Modify | `_build_payload` reasoning_effort; `chat`/`chat_stream` signature; `get_llm_provider` mode routing |
| `backend/api/chat.py` | Modify | Wire mode + reasoning_effort into both streaming and non-streaming call sites |
| `backend/tests/test_model_routing.py` | Create | TDD tests: payload injection, provider model selection |

---

## Task 1: Update Config and Environment

**Files:**
- Modify: `.env` (project root — NOT committed)
- Modify: `.env.example` (project root — committed)
- Modify: `backend/config.py`

- [ ] **Step 1: Update `.env` with new credentials and fast model**

  Open `.env` (at project root, same level as `backend/`) and set:
  ```
  NVIDIA_API_KEY=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
  NVIDIA_MODEL=mistralai/mistral-large-3-675b-instruct-2512
  NVIDIA_FAST_MODEL=mistralai/mistral-small-4-119b-2603
  ```
  Leave all other keys unchanged.

- [ ] **Step 2: Update `.env.example` to document the new variable**

  Add after the `NVIDIA_MODEL` line:
  ```
  # Fast-mode model (smaller, faster; used when mode=fast)
  NVIDIA_FAST_MODEL=mistralai/mistral-small-4-119b-2603
  ```

- [ ] **Step 3: Add new fields to `backend/config.py`**

  In `class Settings(BaseSettings)`, find the `# ── NVIDIA NIM ───` block (around line 24). After `nvidia_embed_model`, add:
  ```python
  nvidia_fast_model: str = "mistralai/mistral-small-4-119b-2603"
  nvidia_fast_reasoning_effort: str = "medium"
  ```

  Then update the two existing lines (around lines 80-82):
  ```python
  # OLD:
  fast_max_tokens: Optional[int] = None  # no hard limit — adaptive budget handles safety
  temperature: float = 0.7

  # NEW:
  fast_max_tokens: Optional[int] = 20000   # fast mode: cap at 20k tokens
  temperature: float = 0.10                # low temperature for precise legal/accounting answers
  ```

- [ ] **Step 4: Verify existing tests still pass (no regressions from config change)**

  Run from `backend/` directory:
  ```
  cd "C:\Users\Armaan\OneDrive - The Era Corporations\Study\Armaan\AI Class\Data Science Class\35. 11-Apr-2026\Project_AccountingLegalChatbot\backend"
  python -m pytest tests/test_adaptive_token_budget.py -v -q
  ```
  Expected: all tests pass. If `test_compute_safe_max_tokens_short_input_honours_requested` fails because `fast_max_tokens` changed from `None` to `20000`, that is expected — it just means the token budget for fast mode now has a cap. The test itself does not read `fast_max_tokens`.

- [ ] **Step 5: Commit config changes**

  ```
  git add backend/config.py .env.example
  git commit -m "config: add nvidia_fast_model, fast reasoning_effort; set fast_max_tokens=20000, temperature=0.10"
  ```
  Note: `.env` is gitignored — do NOT add it.

---

## Task 2: TDD — `_build_payload` reasoning_effort injection

**Files:**
- Create: `backend/tests/test_model_routing.py`
- Modify: `backend/core/llm_manager.py` (lines 201-216)

- [ ] **Step 1: Create test file with two failing tests**

  Create `backend/tests/test_model_routing.py`:
  ```python
  """Tests for two-model mode routing: reasoning_effort payload and provider selection."""
  from unittest.mock import patch

  import pytest

  from config import settings
  from core.llm_manager import NvidiaProvider, get_llm_provider


  # ── Helper ────────────────────────────────────────────────────────────

  def _nvidia_provider(model: str) -> NvidiaProvider:
      return NvidiaProvider(
          api_key="test-key",
          model=model,
          base_url="https://test.nvidia.com/v1",
      )


  _MSGS = [{"role": "user", "content": "What is VAT?"}]


  # ── _build_payload: reasoning_effort ─────────────────────────────────

  def test_reasoning_effort_injected_when_set():
      """reasoning_effort='medium' must appear in the payload dict."""
      provider = _nvidia_provider("mistralai/mistral-small-4-119b-2603")
      payload = provider._build_payload(
          _MSGS, max_tokens=100, temperature=0.1, stream=False, reasoning_effort="medium"
      )
      assert payload["reasoning_effort"] == "medium"


  def test_reasoning_effort_absent_when_none():
      """No reasoning_effort key must appear when reasoning_effort=None."""
      provider = _nvidia_provider("mistralai/mistral-large-3-675b-instruct-2512")
      payload = provider._build_payload(
          _MSGS, max_tokens=100, temperature=0.1, stream=False, reasoning_effort=None
      )
      assert "reasoning_effort" not in payload
  ```

- [ ] **Step 2: Run tests to confirm they fail**

  ```
  cd "C:\Users\Armaan\OneDrive - The Era Corporations\Study\Armaan\AI Class\Data Science Class\35. 11-Apr-2026\Project_AccountingLegalChatbot\backend"
  python -m pytest tests/test_model_routing.py::test_reasoning_effort_injected_when_set tests/test_model_routing.py::test_reasoning_effort_absent_when_none -v
  ```
  Expected: both FAIL with `TypeError: _build_payload() got an unexpected keyword argument 'reasoning_effort'`

- [ ] **Step 3: Add `reasoning_effort` to `_build_payload` in `backend/core/llm_manager.py`**

  Find the `_build_payload` method (around line 201). Replace the entire method:
  ```python
  def _build_payload(
      self,
      messages,
      max_tokens,
      temperature,
      stream: bool,
      reasoning_effort: Optional[str] = None,
  ) -> dict:
      payload: dict = {
          "model": self.model,
          "messages": messages,
          "temperature": temperature,
          "top_p": 1.00,
          "frequency_penalty": 0.00,
          "presence_penalty": 0.00,
          "stream": stream,
      }
      if max_tokens is not None:
          payload["max_tokens"] = max_tokens
      if reasoning_effort is not None:
          payload["reasoning_effort"] = reasoning_effort
      # enable_thinking is incompatible with vision/multimodal inputs — skip for image requests
      if self._is_gemma and not self._messages_contain_images(messages):
          payload["chat_template_kwargs"] = {"enable_thinking": True}
      return payload
  ```

- [ ] **Step 4: Run tests to confirm they pass**

  ```
  python -m pytest tests/test_model_routing.py::test_reasoning_effort_injected_when_set tests/test_model_routing.py::test_reasoning_effort_absent_when_none -v
  ```
  Expected: both PASS.

- [ ] **Step 5: Commit**

  ```
  git add backend/tests/test_model_routing.py backend/core/llm_manager.py
  git commit -m "feat(llm): add reasoning_effort parameter to NvidiaProvider._build_payload"
  ```

---

## Task 3: TDD — `reasoning_effort` flows through `chat` and `chat_stream`

**Files:**
- Modify: `backend/tests/test_model_routing.py` (add tests)
- Modify: `backend/core/llm_manager.py` — `NvidiaProvider.chat` and `NvidiaProvider.chat_stream`; `BaseLLMProvider.chat` and `BaseLLMProvider.chat_stream` abstract signatures

- [ ] **Step 1: Add two failing tests to `backend/tests/test_model_routing.py`**

  Append to the existing file (after the last test):
  ```python
  # ── chat / chat_stream signatures accept reasoning_effort ─────────────

  def test_chat_accepts_reasoning_effort_kwarg():
      """NvidiaProvider.chat must accept reasoning_effort without raising TypeError."""
      from unittest.mock import AsyncMock, patch, MagicMock
      import asyncio

      provider = _nvidia_provider("mistralai/mistral-small-4-119b-2603")

      mock_response = MagicMock()
      mock_response.status_code = 200
      mock_response.json.return_value = {
          "choices": [{"message": {"content": "Answer"}, "finish_reason": "stop"}],
          "model": "mistralai/mistral-small-4-119b-2603",
          "usage": {"total_tokens": 10},
      }

      async def _run():
          with patch("httpx.AsyncClient") as mock_client_cls:
              mock_client = AsyncMock()
              mock_client.__aenter__ = AsyncMock(return_value=mock_client)
              mock_client.__aexit__ = AsyncMock(return_value=False)
              mock_client.post = AsyncMock(return_value=mock_response)
              mock_client_cls.return_value = mock_client
              # Should not raise TypeError
              result = await provider.chat(
                  _MSGS,
                  temperature=0.1,
                  max_tokens=100,
                  reasoning_effort="medium",
              )
              return result

      result = asyncio.get_event_loop().run_until_complete(_run())
      assert result.content == "Answer"


  def test_chat_stream_accepts_reasoning_effort_kwarg():
      """NvidiaProvider.chat_stream must accept reasoning_effort without raising TypeError."""
      import asyncio

      provider = _nvidia_provider("mistralai/mistral-small-4-119b-2603")

      # Verify the signature accepts the kwarg — generator construction alone is enough
      gen = provider.chat_stream(_MSGS, temperature=0.1, max_tokens=100, reasoning_effort="medium")
      # It's an async generator; just confirm it was created without TypeError
      assert gen is not None
  ```

- [ ] **Step 2: Run to confirm they fail**

  ```
  python -m pytest tests/test_model_routing.py::test_chat_accepts_reasoning_effort_kwarg tests/test_model_routing.py::test_chat_stream_accepts_reasoning_effort_kwarg -v
  ```
  Expected: both FAIL with `TypeError: ... got an unexpected keyword argument 'reasoning_effort'`

- [ ] **Step 3: Update `BaseLLMProvider` abstract method signatures in `backend/core/llm_manager.py`**

  Find `BaseLLMProvider.chat` (around line 153) and update:
  ```python
  async def chat(
      self,
      messages: list[dict],
      temperature: float = 0.7,
      max_tokens: Optional[int] = None,
      reasoning_effort: Optional[str] = None,
  ) -> LLMResponse:
      """Non-streaming chat. Use chat_stream() for streaming responses."""
      raise NotImplementedError
  ```

  Find `BaseLLMProvider.chat_stream` (around line 162) and update:
  ```python
  async def chat_stream(
      self,
      messages: list[dict],
      temperature: float = 0.7,
      max_tokens: Optional[int] = None,
      reasoning_effort: Optional[str] = None,
  ) -> AsyncGenerator[str, None]:
      raise NotImplementedError
      yield  # make it a generator
  ```

- [ ] **Step 4: Update `NvidiaProvider.chat` in `backend/core/llm_manager.py`**

  Find `NvidiaProvider.chat` (around line 218). Change signature and the `_build_payload` call:
  ```python
  async def chat(self, messages, temperature=0.7, max_tokens=None, reasoning_effort=None):
      headers = {
          "Authorization": f"Bearer {self.api_key}",
          "Content-Type": "application/json",
      }
      payload = self._build_payload(
          messages, max_tokens, temperature, stream=False, reasoning_effort=reasoning_effort
      )
      # ... rest of the method unchanged ...
  ```
  (Only change the `def` line and the `_build_payload(...)` call — leave all retry/timeout logic as-is.)

- [ ] **Step 5: Update `NvidiaProvider.chat_stream` in `backend/core/llm_manager.py`**

  Find `NvidiaProvider.chat_stream` (around line 268). Change signature and the `_build_payload` call:
  ```python
  async def chat_stream(self, messages, temperature=0.7, max_tokens=None, reasoning_effort=None):
      headers = {
          "Authorization": f"Bearer {self.api_key}",
          "Content-Type": "application/json",
          "Accept": "text/event-stream",
      }
      payload = self._build_payload(
          messages, max_tokens, temperature, stream=True, reasoning_effort=reasoning_effort
      )
      # ... rest of the method unchanged ...
  ```

- [ ] **Step 6: Run tests to confirm they pass**

  ```
  python -m pytest tests/test_model_routing.py -v
  ```
  Expected: all 4 tests PASS.

- [ ] **Step 7: Commit**

  ```
  git add backend/tests/test_model_routing.py backend/core/llm_manager.py
  git commit -m "feat(llm): add reasoning_effort param to chat/chat_stream signatures"
  ```

---

## Task 4: TDD — `get_llm_provider` mode-based model routing

**Files:**
- Modify: `backend/tests/test_model_routing.py` (add tests)
- Modify: `backend/core/llm_manager.py` — `get_llm_provider` function (lines 711-731)

- [ ] **Step 1: Add two failing tests to `backend/tests/test_model_routing.py`**

  Append to the existing file:
  ```python
  # ── get_llm_provider: mode-based routing ─────────────────────────────

  def test_fast_mode_returns_fast_model_for_nvidia():
      """mode='fast' with nvidia provider must use nvidia_fast_model."""
      with (
          patch.object(settings, "llm_provider", "nvidia"),
          patch.object(settings, "nvidia_fast_model", "mistralai/mistral-small-4-119b-2603"),
          patch.object(settings, "nvidia_model", "mistralai/mistral-large-3-675b-instruct-2512"),
          patch.object(settings, "nvidia_api_key", "test-key"),
          patch.object(settings, "nvidia_base_url", "https://integrate.api.nvidia.com/v1"),
      ):
          provider = get_llm_provider(mode="fast")
          assert provider.model == "mistralai/mistral-small-4-119b-2603"


  def test_analyst_mode_returns_main_model_for_nvidia():
      """mode='analyst' with nvidia provider must use nvidia_model (large model)."""
      with (
          patch.object(settings, "llm_provider", "nvidia"),
          patch.object(settings, "nvidia_model", "mistralai/mistral-large-3-675b-instruct-2512"),
          patch.object(settings, "nvidia_api_key", "test-key"),
          patch.object(settings, "nvidia_base_url", "https://integrate.api.nvidia.com/v1"),
      ):
          provider = get_llm_provider(mode="analyst")
          assert provider.model == "mistralai/mistral-large-3-675b-instruct-2512"
  ```

- [ ] **Step 2: Run to confirm they fail**

  ```
  python -m pytest tests/test_model_routing.py::test_fast_mode_returns_fast_model_for_nvidia tests/test_model_routing.py::test_analyst_mode_returns_main_model_for_nvidia -v
  ```
  Expected: `test_fast_mode_returns_fast_model_for_nvidia` FAILS (mode arg not supported); `test_analyst_mode_returns_main_model_for_nvidia` FAILS (mode arg not supported).

- [ ] **Step 3: Update `get_llm_provider` in `backend/core/llm_manager.py`**

  Find `get_llm_provider` (around line 711). Replace the entire function:
  ```python
  def get_llm_provider(
      provider_name: Optional[str] = None,
      mode: Optional[str] = None,
  ) -> BaseLLMProvider:
      """
      Factory function – returns an LLM provider instance.

      Args:
          provider_name: Override the default provider from settings.
                         If None, uses settings.llm_provider.
          mode: Chat mode ('fast', 'analyst', 'deep_research'). When 'fast'
                and the active provider is NVIDIA, returns a provider built
                with ``settings.nvidia_fast_model`` instead of the main model.

      Returns:
          An instance of BaseLLMProvider ready to call .chat() or .chat_stream().
      """
      name = (provider_name or settings.llm_provider).lower()

      # Fast mode on NVIDIA: use the smaller, faster model
      if name == "nvidia" and mode == "fast":
          provider = NvidiaProvider(
              api_key=settings.nvidia_api_key,
              model=settings.nvidia_fast_model,
              base_url=settings.nvidia_base_url,
          )
          logger.info(
              "LLM provider initialized: %s / %s [fast mode]",
              provider.provider_name,
              provider.model,
          )
          return provider

      factory = _PROVIDER_MAP.get(name)
      if not factory:
          raise ValueError(
              f"Unknown LLM provider '{name}'. "
              f"Available: {list(_PROVIDER_MAP.keys())}"
          )
      provider = factory()
      logger.info(
          "LLM provider initialized: %s / %s",
          provider.provider_name,
          provider.model,
      )
      return provider
  ```

- [ ] **Step 4: Run tests to confirm they pass**

  ```
  python -m pytest tests/test_model_routing.py -v
  ```
  Expected: all 6 tests PASS.

- [ ] **Step 5: Commit**

  ```
  git add backend/tests/test_model_routing.py backend/core/llm_manager.py
  git commit -m "feat(llm): get_llm_provider accepts mode param; fast mode uses nvidia_fast_model"
  ```

---

## Task 5: Wire mode routing into `chat.py` — both endpoints

**Files:**
- Modify: `backend/api/chat.py` — two `get_llm_provider` call sites + two `chat_stream`/`chat` call sites

- [ ] **Step 1: Update the streaming endpoint — provider instantiation (line ~466)**

  Find this line (inside the streaming SSE endpoint):
  ```python
  _llm = get_llm_provider(req.provider)
  ```
  Replace with:
  ```python
  _llm = get_llm_provider(req.provider, mode=req.mode)
  _reasoning_effort = (
      settings.nvidia_fast_reasoning_effort if req.mode == "fast" else None
  )
  ```

- [ ] **Step 2: Update the streaming endpoint — `chat_stream` call (line ~639)**

  Find (inside the streaming SSE endpoint):
  ```python
  async for chunk in _llm.chat_stream(
      _msgs,
      temperature=settings.temperature,
      max_tokens=_safe_max,
  ):
  ```
  Replace with:
  ```python
  async for chunk in _llm.chat_stream(
      _msgs,
      temperature=settings.temperature,
      max_tokens=_safe_max,
      reasoning_effort=_reasoning_effort,
  ):
  ```

- [ ] **Step 3: Update the non-streaming endpoint — provider instantiation (line ~762)**

  Find (inside the non-streaming endpoint):
  ```python
  llm = get_llm_provider(req.provider)  # single instantiation, used for both classifier and main LLM
  ```
  Replace with:
  ```python
  llm = get_llm_provider(req.provider, mode=req.mode)  # mode selects fast or main model
  _reasoning_effort = (
      settings.nvidia_fast_reasoning_effort if req.mode == "fast" else None
  )
  ```

- [ ] **Step 4: Update the non-streaming endpoint — `llm.chat` call (line ~874)**

  Find (inside the non-streaming endpoint):
  ```python
  response = await llm.chat(
      messages,
      temperature=settings.temperature,
      max_tokens=_safe_max,
  )
  ```
  Replace with:
  ```python
  response = await llm.chat(
      messages,
      temperature=settings.temperature,
      max_tokens=_safe_max,
      reasoning_effort=_reasoning_effort,
  )
  ```

- [ ] **Step 5: Verify no syntax errors**

  ```
  cd "C:\Users\Armaan\OneDrive - The Era Corporations\Study\Armaan\AI Class\Data Science Class\35. 11-Apr-2026\Project_AccountingLegalChatbot\backend"
  python -c "from api.chat import router; print('OK')"
  ```
  Expected: `OK`

- [ ] **Step 6: Commit**

  ```
  git add backend/api/chat.py
  git commit -m "feat(chat): route fast mode to nvidia_fast_model with reasoning_effort=medium"
  ```

---

## Task 6: Full Test Suite Verification

**Files:** None — verification only.

- [ ] **Step 1: Run the complete test suite**

  ```
  cd "C:\Users\Armaan\OneDrive - The Era Corporations\Study\Armaan\AI Class\Data Science Class\35. 11-Apr-2026\Project_AccountingLegalChatbot\backend"
  python -m pytest --tb=short -q
  ```
  Expected: all tests pass (470+ passed, 0 failed). Note the exact count and report it.

- [ ] **Step 2: If any tests fail, read the error output carefully**

  - Failures in `test_adaptive_token_budget.py` related to `fast_max_tokens`: re-check whether the test reads `settings.fast_max_tokens` directly. If so, the test now expects `20000` — update the assertion.
  - Failures in `test_model_routing.py`: re-check the mock patches — ensure `patch.object` targets the `settings` singleton imported in the test file.
  - Failures in `test_chat_web_ingestion.py`: re-check whether `get_llm_provider` is mocked — the new `mode` argument has a default of `None`, so existing mocks should still work.

- [ ] **Step 3: Final commit if any test fixes were needed**

  ```
  git add -A
  git commit -m "test: fix test assertions after temperature and fast_max_tokens config update"
  ```

- [ ] **Step 4: Confirm the feature is working end-to-end**

  The backend server must be running. Send a fast-mode message and check the logs:
  ```
  # In logs you should see:
  # LLM provider initialized: nvidia / mistralai/mistral-small-4-119b-2603 [fast mode]
  # (for fast requests)
  # LLM provider initialized: nvidia / mistralai/mistral-large-3-675b-instruct-2512
  # (for analyst/deep_research requests)
  ```
