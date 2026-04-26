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


# ── chat / chat_stream signatures accept reasoning_effort ─────────────

async def test_chat_accepts_reasoning_effort_kwarg():
    """NvidiaProvider.chat must accept reasoning_effort without raising TypeError."""
    from unittest.mock import AsyncMock, MagicMock

    provider = _nvidia_provider("mistralai/mistral-small-4-119b-2603")

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "choices": [{"message": {"content": "Answer"}, "finish_reason": "stop"}],
        "model": "mistralai/mistral-small-4-119b-2603",
        "usage": {"total_tokens": 10},
    }

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
        assert result.content == "Answer"


def test_chat_stream_accepts_reasoning_effort_kwarg():
    """NvidiaProvider.chat_stream must accept reasoning_effort without raising TypeError."""
    provider = _nvidia_provider("mistralai/mistral-small-4-119b-2603")

    # Verify the signature accepts the kwarg — generator construction alone is enough
    gen = provider.chat_stream(_MSGS, temperature=0.1, max_tokens=100, reasoning_effort="medium")
    # It's an async generator; just confirm it was created without TypeError
    assert gen is not None


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


def test_default_mode_returns_main_model_for_nvidia():
    """mode=None (the real default) must use nvidia_model, not nvidia_fast_model."""
    with (
        patch.object(settings, "llm_provider", "nvidia"),
        patch.object(settings, "nvidia_model", "mistralai/mistral-large-3-675b-instruct-2512"),
        patch.object(settings, "nvidia_fast_model", "mistralai/mistral-small-4-119b-2603"),
        patch.object(settings, "nvidia_api_key", "test-key"),
        patch.object(settings, "nvidia_base_url", "https://integrate.api.nvidia.com/v1"),
    ):
        provider = get_llm_provider()          # no mode argument at all
        assert provider.model == "mistralai/mistral-large-3-675b-instruct-2512"


def test_fast_mode_non_nvidia_falls_through_to_main_model():
    """mode='fast' with a non-NVIDIA provider must fall through to the main model."""
    # Only run this test if openai provider is available in the provider map.
    # We patch the factory to avoid needing real OpenAI credentials.
    from unittest.mock import MagicMock
    mock_openai_provider = MagicMock()
    mock_openai_provider.model = "gpt-4o"
    mock_openai_factory = MagicMock(return_value=mock_openai_provider)

    from core.llm_manager import _PROVIDER_MAP
    original = _PROVIDER_MAP.get("openai")
    try:
        _PROVIDER_MAP["openai"] = mock_openai_factory
        with patch.object(settings, "llm_provider", "openai"):
            provider = get_llm_provider(mode="fast")
            assert provider.model == "gpt-4o"
    finally:
        if original is not None:
            _PROVIDER_MAP["openai"] = original
        elif "openai" in _PROVIDER_MAP:
            del _PROVIDER_MAP["openai"]
