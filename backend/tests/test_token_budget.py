"""Tests that config and sliding-context use the correct token budget settings."""
import inspect
from config import Settings
from api.chat import _build_sliding_context


def test_default_max_tokens_is_none():
    """max_tokens must be None — no hard limit, model uses its full capacity."""
    field = Settings.model_fields.get("max_tokens")
    assert field is not None, "max_tokens field not found in Settings"
    assert field.default is None, f"Expected None, got {field.default}"


def test_default_top_k_results_is_8():
    """top_k_results global default must be 8 for analyst/deep_research modes."""
    field = Settings.model_fields.get("top_k_results")
    assert field is not None, "top_k_results field not found in Settings"
    assert field.default == 8, f"Expected 8, got {field.default}"


def test_fast_max_tokens_is_20000():
    """fast_max_tokens must be 20000 — caps fast-mode responses for mistral-small."""
    field = Settings.model_fields.get("fast_max_tokens")
    assert field is not None, "fast_max_tokens field not found in Settings"
    assert field.default == 20000, f"Expected 20000, got {field.default}"


def test_fast_top_k_is_15():
    """fast_top_k must be 15 for broader RAG coverage in fast mode."""
    field = Settings.model_fields.get("fast_top_k")
    assert field is not None, "fast_top_k field not found in Settings"
    assert field.default == 15, f"Expected 15, got {field.default}"


def test_sliding_context_default_is_12000():
    """_build_sliding_context default max_tokens_estimate must be 12000."""
    sig = inspect.signature(_build_sliding_context)
    param = sig.parameters.get("max_tokens_estimate")
    assert param is not None, "max_tokens_estimate param not found"
    assert param.default == 12000, f"Expected 12000, got {param.default}"
