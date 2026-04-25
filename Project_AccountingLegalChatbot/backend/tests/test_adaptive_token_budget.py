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
