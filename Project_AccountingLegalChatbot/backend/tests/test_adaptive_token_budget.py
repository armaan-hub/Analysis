"""Tests for adaptive token budgeting in BaseLLMProvider."""
from core.llm_manager import BaseLLMProvider, _CONTEXT_WINDOWS


class _ConcreteProvider(BaseLLMProvider):
    """Minimal concrete provider for testing BaseLLMProvider methods."""
    async def chat(self, messages, temperature=0.7, max_tokens=None):
        raise NotImplementedError

    async def chat_stream(self, messages, temperature=0.7, max_tokens=None):
        raise NotImplementedError
        yield


def make_provider(model: str) -> _ConcreteProvider:
    return _ConcreteProvider(api_key="test", model=model)


# ── Registry ─────────────────────────────────────────────────────────

def test_registry_has_minimum_required_families():
    """Guards against accidental deletion of key model families."""
    required = {"mistral-large", "gpt-4o", "claude", "llama-3.1", "gemma-3"}
    assert required.issubset(_CONTEXT_WINDOWS.keys())


def test_gpt4o_not_shadowed_by_gpt4():
    """gpt-4o must match the 128K entry, not the 8K gpt-4 entry."""
    p = make_provider("openai/gpt-4o-2024-11-20")
    assert p.get_context_window() == 128_000


def test_llama31_not_shadowed_by_llama3():
    """Versioned llama-3.1 must match 128K, not base llama-3 at 8K."""
    p = make_provider("meta/llama-3.1-70b-instruct")
    assert p.get_context_window() == 131_072


def test_get_context_window_known_mistral_large():
    p = make_provider("mistralai/mistral-large-3-675b-instruct-2512")
    assert p.get_context_window() == 131_072


def test_get_context_window_known_claude():
    p = make_provider("anthropic/claude-3-5-sonnet")
    assert p.get_context_window() == 200_000


def test_get_context_window_unknown_model_returns_fallback():
    p = make_provider("some-unknown-model-xyz")
    assert p.get_context_window() == 8_192


def test_get_context_window_substring_case_insensitive():
    # Registry lookup is case-insensitive
    p = make_provider("MISTRAL-LARGE-3-test")
    assert p.get_context_window() == 131_072


# ── compute_safe_max_tokens ───────────────────────────────────────────

_MISTRAL_LARGE_WINDOW = 131_072   # from registry


def test_compute_safe_max_tokens_short_input_honours_requested():
    """Short input: available is huge → clamp to requested_max."""
    p = make_provider("mistralai/mistral-large-3-675b-instruct-2512")
    msgs = [{"role": "user", "content": "Hello"}]  # ~2 tokens
    result = p.compute_safe_max_tokens(msgs, requested_max=4096)
    assert result == 4096


def test_compute_safe_max_tokens_no_requested_max_returns_available():
    """No ceiling → returns available tokens (context_window - input - buffer)."""
    p = make_provider("mistralai/mistral-large-3-675b-instruct-2512")
    msgs = [{"role": "user", "content": "Hello"}]
    result = p.compute_safe_max_tokens(msgs, requested_max=None)
    # available = 131072 - (5//4) - 500 = 130571
    assert result == _MISTRAL_LARGE_WINDOW - (5 // 4) - 500


def test_compute_safe_max_tokens_long_input_reduces_budget():
    """Long input near the limit → available < requested_max, so available wins."""
    p = make_provider("mistralai/mistral-large-3-675b-instruct-2512")
    # 520000 chars ÷ 4 = 130000 tokens input → available = 131072-130000-500 = 572
    content = "x" * 520_000
    msgs = [{"role": "user", "content": content}]
    result = p.compute_safe_max_tokens(msgs, requested_max=4096)
    assert result == 572


def test_compute_safe_max_tokens_overflow_returns_minimum():
    """Input exceeds context window → return minimum viable (256)."""
    p = make_provider("mistralai/mistral-large-3-675b-instruct-2512")
    # 531000 chars ÷ 4 = 132750 tokens > 131072 window → available < 0 → 256
    content = "x" * 531_000
    msgs = [{"role": "user", "content": content}]
    result = p.compute_safe_max_tokens(msgs, requested_max=4096)
    assert result == 256


def test_compute_safe_max_tokens_none_content_treated_as_empty():
    """Message with None content should not raise; treated as 0 chars."""
    p = make_provider("mistralai/mistral-large-3-675b-instruct-2512")
    msgs = [{"role": "system", "content": None}, {"role": "user", "content": "Hi"}]
    result = p.compute_safe_max_tokens(msgs, requested_max=1000)
    assert result == 1000


def test_compute_safe_max_tokens_fallback_model():
    """Unknown model uses 8192 window fallback."""
    p = make_provider("some-unknown-model-xyz")
    msgs = [{"role": "user", "content": "Hello"}]
    result = p.compute_safe_max_tokens(msgs, requested_max=2048)
    # available = 8192 - (5//4) - 500 = 7691 > 2048 → returns 2048
    assert result == 2048
