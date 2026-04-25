"""Tests for adaptive token budgeting in BaseLLMProvider."""
import pytest
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

def test_context_windows_registry_is_not_empty():
    assert len(_CONTEXT_WINDOWS) > 0


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
