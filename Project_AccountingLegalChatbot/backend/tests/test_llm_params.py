"""Tests for compute_llm_params() — per-model-family, per-mode LLM parameter selection."""
import pytest
from config import compute_llm_params, LLMParams


class TestComputeLlmParamsFamilyDetection:
    """Verify correct family is detected from model name."""

    def test_claude_family_fast(self):
        p = compute_llm_params("claude-sonnet-4-20250514", "fast")
        assert p["max_tokens"] == 8192
        assert p["temperature"] == 0.3
        assert p["timeout"] == 90.0
        assert p["top_k"] == 8

    def test_claude_family_deep_research(self):
        p = compute_llm_params("claude-sonnet-4", "deep_research")
        assert p["max_tokens"] == 32768
        assert p["temperature"] == 0.4
        assert p["timeout"] == 300.0
        assert p["top_k"] == 20

    def test_gpt4_family(self):
        p = compute_llm_params("gpt-4o", "analyst")
        assert p["max_tokens"] == 32768
        assert p["top_k"] == 16

    def test_gpt35_family_lower_budget(self):
        p = compute_llm_params("gpt-3.5-turbo", "fast")
        assert p["max_tokens"] == 4096
        assert p["timeout"] == 30.0

    def test_mistral_model_via_nvidia(self):
        p = compute_llm_params("mistralai/mistral-large-3-675b-instruct-2512", "fast")
        assert p["max_tokens"] == 8192
        assert p["timeout"] == 90.0

    def test_devstral_is_mistral_family(self):
        p = compute_llm_params("mistralai/devstral-2-123b-instruct-2512", "deep_research")
        assert p["max_tokens"] == 32768

    def test_ollama_llama(self):
        p = compute_llm_params("llama3", "fast")
        assert p["timeout"] == 180.0  # ollama is slower

    def test_lmstudio_local(self):
        p = compute_llm_params("qwen/qwen3-vl-30b", "analyst")
        assert p["timeout"] == 900.0

    def test_groq_capped_tokens(self):
        p = compute_llm_params("llama-3.3-70b-versatile", "deep_research")
        assert p["max_tokens"] == 16384  # groq cap

    def test_nvidia_embed_model_uses_nvidia_family(self):
        p = compute_llm_params("nvidia/nv-embedqa-e5-v5", "fast")
        assert p["max_tokens"] == 8192

    def test_unknown_model_uses_default(self):
        p = compute_llm_params("some-random-model-v99", "fast")
        assert p["max_tokens"] == 4096  # default fast

    def test_invalid_mode_falls_back_to_fast(self):
        p = compute_llm_params("claude-sonnet-4", "invalid_mode")
        assert p["max_tokens"] == 8192  # claude fast

    def test_returns_llmparams_typed_dict_keys(self):
        p = compute_llm_params("gpt-4o", "fast")
        assert set(p.keys()) == {"max_tokens", "temperature", "timeout", "top_k"}
