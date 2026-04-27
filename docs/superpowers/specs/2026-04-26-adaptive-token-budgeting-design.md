# Adaptive Token Budgeting — Design Spec

**Date:** 2026-04-26  
**Status:** Approved

---

## Problem

The NVIDIA NIM API returns HTTP 400 on the second message in a conversation when
`max_tokens` in the request exceeds the model's remaining context capacity.
The root cause: the output token ceiling (`fast_max_tokens=8192` previously, now `None`)
combined with a long conversation history pushes `input_tokens + max_tokens`
over the model's total context window limit.

---

## Goal

Every LLM request must automatically compute a safe output token ceiling based on:
1. The actual context window of the model in use
2. The estimated size of the current input (messages)
3. A safety buffer to avoid off-by-one edge cases

No 400 errors from token overflow. No artificial ceiling that truncates long legal/accounting responses unnecessarily.

---

## Architecture

### Location: `backend/core/llm_manager.py`

Three additions to the existing provider hierarchy:

**1. Module-level `_CONTEXT_WINDOWS: dict[str, int]`**  
Maps model-name substrings to context window sizes (in tokens).  
Lookup uses substring matching — e.g. `"mistral-large"` matches
`"mistralai/mistral-large-3-675b-instruct-2512"`.  
Falls back to `8192` if no pattern matches (conservative safe default).

**2. `BaseLLMProvider.get_context_window() -> int`**  
Iterates `_CONTEXT_WINDOWS`, returns the window for the first key found
as a substring of `self.model`. Returns `8192` as fallback.

**3. `BaseLLMProvider.compute_safe_max_tokens(messages, requested_max=None) -> int | None`**  
```
input_chars   = sum(len(msg.get("content") or "") for msg in messages)
input_tokens  = input_chars // 4          # 4 chars ≈ 1 token
safety_buffer = 500                        # never cut it to the wire
available     = context_window − input_tokens − safety_buffer

if available <= 0:
    return 256                             # minimum viable response

if requested_max is None:
    return available                       # uncapped — use all remaining space

return min(requested_max, available)       # honour caller's ceiling
```

### Location: `backend/api/chat.py`

One-line change in the `generate()` SSE handler.  
Before (line ~640):
```python
max_tokens=settings.fast_max_tokens if req.mode == "fast" else settings.max_tokens,
```
After:
```python
_requested = settings.fast_max_tokens if req.mode == "fast" else settings.max_tokens
max_tokens=_llm.compute_safe_max_tokens(_msgs, _requested),
```

---

## Context Window Registry (initial values)

| Pattern (substring) | Context Window |
|---|---|
| `mistral-large` | 131 072 |
| `mistral-small` | 32 768 |
| `mistral-medium` | 131 072 |
| `mixtral` | 32 768 |
| `gemma-4` | 131 072 |
| `gemma-3` | 32 768 |
| `llama-3.3` | 131 072 |
| `llama-3.2` | 131 072 |
| `llama-3.1` | 131 072 |
| `llama-3` | 8 192 |
| `llama3.2` | 131 072 |
| `llama3.1` | 131 072 |
| `llama3` | 8 192 |
| `gpt-4o` | 128 000 |
| `gpt-4-turbo` | 128 000 |
| `gpt-4` | 8 192 |
| `gpt-3.5-turbo-16k` | 16 385 |
| `gpt-3.5` | 16 385 |
| `claude` | 200 000 |
| `nemotron` | 128 000 |
| **fallback (no match)** | **8 192** |

---

## Error Handling

- If `compute_safe_max_tokens` returns `256`, the model still responds — a minimal
  answer is better than a 400 error.
- The existing friendly HTTP-error handler in `chat.py` remains as a backstop for
  any remaining API errors.

---

## Testing

Unit tests in `backend/tests/test_adaptive_token_budget.py`:

1. `test_get_context_window_known_model` — mistral-large-3-675b → 131072
2. `test_get_context_window_unknown_model` — some-unknown-model → 8192 (fallback)
3. `test_get_context_window_substring_match` — nvidia/llama-3.1-nemotron → 131072
4. `test_compute_safe_max_tokens_short_input` — short messages → returns requested_max
5. `test_compute_safe_max_tokens_long_input` — input near context limit → returns small available
6. `test_compute_safe_max_tokens_overflow` — input exceeds window → returns 256
7. `test_compute_safe_max_tokens_no_requested_max` — None ceiling → returns full available

Integration test (existing `test_chat_web_ingestion.py` already mocks `chat_stream`
so no 400 paths occur there — no change needed).

---

## Non-Goals

- Dynamic context window discovery via API (deferred — static table is reliable and fast)
- Per-request token counting via tiktoken (overkill; char÷4 is accurate enough for budgeting)
- Changing any provider other than NvidiaProvider's actual streaming behaviour

---

## Files Changed

| File | Change |
|---|---|
| `backend/core/llm_manager.py` | Add `_CONTEXT_WINDOWS`, `get_context_window()`, `compute_safe_max_tokens()` |
| `backend/api/chat.py` | Use `compute_safe_max_tokens` at the `chat_stream` call site |
| `backend/tests/test_adaptive_token_budget.py` | New test file — 7 unit tests |
