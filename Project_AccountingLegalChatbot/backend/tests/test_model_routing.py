"""Tests for two-model mode routing: reasoning_effort payload and provider selection."""
from unittest.mock import patch  # used in Task 3+ tests (provider selection)

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
