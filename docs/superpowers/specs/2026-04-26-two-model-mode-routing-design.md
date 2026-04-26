# Two-Model Mode Routing Design

**Date:** 2026-04-26  
**Status:** Approved

## Problem

All chat modes (Fast, Analyst, Deep Research) currently use the same model:
`mistralai/mistral-large-3-675b-instruct-2512`. This means Fast mode is as slow as a
full deep-research query — there is no speed/quality trade-off available.

## Solution

Route **Fast mode** to a smaller, faster reasoning model (`mistral-small-4-119b-2603`),
and keep **Analyst / Deep Research / Council** on the powerful large model
(`mistral-large-3-675b-instruct-2512`). `mistral-small-4-119b-2603` natively supports a
`reasoning_effort` parameter; setting it to `"medium"` gives quality answers while
staying significantly faster than the 675B model.

## Model Assignments

| Mode | Model | reasoning_effort | max_tokens | timeout |
|------|-------|-----------------|------------|---------|
| Fast | `mistralai/mistral-small-4-119b-2603` | `"medium"` | 20 000 | streaming (read=None) |
| Analyst | `mistralai/mistral-large-3-675b-instruct-2512` | *(not set)* | None (unlimited) | streaming (read=None) |
| Deep Research | `mistralai/mistral-large-3-675b-instruct-2512` | *(not set)* | None (unlimited) | streaming (read=None) |
| Council *(runs inside Analyst / Deep Research)* | `mistralai/mistral-large-3-675b-instruct-2512` | *(not set)* | None (unlimited) | streaming (read=None) |

Temperature for all modes: `0.10` (low temperature → precise, factual answers for
legal/accounting domain).

Both models share the same NVIDIA NIM API key (platform-level, not model-level).

## Architecture

Council is not a separate mode. It runs as an orchestration layer within Analyst and Deep
Research modes; the model selection follows those modes' settings.

```
ChatRequest.mode
    ├── "fast"          → NvidiaProvider(nvidia_fast_model)  + reasoning_effort="medium"
    ├── "analyst"       → NvidiaProvider(nvidia_model)       (no reasoning_effort)
    └── "deep_research" → NvidiaProvider(nvidia_model)       (no reasoning_effort)
```

Two `NvidiaProvider` instances are created at startup (or on first request) by the
`get_llm_provider(mode)` factory function.

## Files Changed

### `.env`
```
NVIDIA_API_KEY=<new key>
NVIDIA_FAST_MODEL=mistralai/mistral-small-4-119b-2603
```

### `backend/config.py`
New fields added to `Settings`:
```python
nvidia_fast_model: str = "mistralai/mistral-small-4-119b-2603"
nvidia_fast_reasoning_effort: str = "medium"
fast_max_tokens: Optional[int] = 20000   # was None
temperature: float = 0.10               # was 0.7
# max_tokens stays None (unlimited) for analyst/deep_research
```

### `backend/core/llm_manager.py`

1. `_build_payload` — accept optional `reasoning_effort: str | None = None` parameter;
   inject `"reasoning_effort"` key into payload when not None.

2. `chat` and `chat_stream` — accept optional `reasoning_effort` parameter; pass through
   to `_build_payload`.

3. `get_llm_provider(mode: str) -> BaseLLMProvider` — new factory function:
   - `mode == "fast"` → `NvidiaProvider(api_key, nvidia_fast_model, base_url)`
   - all other modes → `NvidiaProvider(api_key, nvidia_model, base_url)`

   No change to provider selection for non-NVIDIA providers (they use the single
   `active_model` as before).

### `backend/api/chat.py`

At both call sites (streaming and non-streaming):
```python
provider = get_llm_provider(mode=req.mode)
reasoning_effort = (
    settings.nvidia_fast_reasoning_effort if req.mode == "fast" else None
)
# pass reasoning_effort to provider.chat_stream / provider.chat
```

## Reasoning Content / Thinking Tokens

NVIDIA NIM returns Mistral thinking content in a separate `reasoning_content` field in
SSE delta chunks. The existing streaming code reads only `delta.get("content", "")` —
thinking tokens are already silently ignored. No stripping logic is needed.

## Token Budget

- Fast mode `max_tokens: 20000` flows through `compute_safe_max_tokens` as
  `requested_max`. The adaptive budget caps it if the context window would overflow,
  but 20 000 output tokens is well within the model's window for typical query sizes.
- Analyst / Deep Research `max_tokens: None` → `compute_safe_max_tokens` returns
  `available` (context_window − input_tokens − buffer), which is the largest safe value.

## Tests

Three tests to add / update:

1. `test_fast_mode_uses_fast_model` — mock `get_llm_provider`; assert `mode="fast"`
   resolves to `nvidia_fast_model` model name.

2. `test_reasoning_effort_injected_for_fast_mode` — call `_build_payload` with
   `reasoning_effort="medium"`; assert key is present in returned dict.

3. `test_reasoning_effort_absent_for_large_model` — call `_build_payload` with
   `reasoning_effort=None`; assert `"reasoning_effort"` key is NOT in returned dict.

## Out of Scope

- UI changes (mode buttons already exist and map correctly)
- Adding `reasoning_effort` to non-NVIDIA providers
- Classifier-based automatic reasoning effort selection per query
