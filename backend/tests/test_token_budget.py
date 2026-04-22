"""Tests that config and sliding-context use the expanded token budget."""
import inspect
from config import Settings
from api.chat import _build_sliding_context


def test_default_max_tokens_is_8192():
    """max_tokens field default must be 8192 for fast mode quality."""
    field = Settings.model_fields.get("max_tokens")
    assert field is not None, "max_tokens field not found in Settings"
    assert field.default == 8192, f"Expected 8192, got {field.default}"


def test_default_top_k_results_is_15():
    """top_k_results field default must be 15 for broader RAG coverage."""
    field = Settings.model_fields.get("top_k_results")
    assert field is not None, "top_k_results field not found in Settings"
    assert field.default == 15, f"Expected 15, got {field.default}"


def test_sliding_context_default_is_12000():
    """_build_sliding_context default max_tokens_estimate must be 12000."""
    sig = inspect.signature(_build_sliding_context)
    param = sig.parameters.get("max_tokens_estimate")
    assert param is not None, "max_tokens_estimate param not found"
    assert param.default == 12000, f"Expected 12000, got {param.default}"
