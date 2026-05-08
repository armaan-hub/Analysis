"""Tests for the no-sources disclaimer when RAG returns 0 results."""
import sys
import pytest

sys.path.insert(0, ".")


def test_disclaimer_prepended_when_no_rag_results():
    """When RAG returns 0 sources, the response includes a disclaimer."""
    from api.chat import _inject_no_sources_disclaimer

    response_text = "Federal Law No. 50 of 2022 governs cheque bounce crimes."
    result = _inject_no_sources_disclaimer(response_text, sources_found=0)
    assert "⚠️" in result or "No matching" in result or "knowledge base" in result, \
        f"Expected disclaimer in response, got: {result[:200]}"
    assert response_text in result, "Original response should be preserved"


def test_no_disclaimer_when_rag_returns_results():
    """When RAG returns sources, no disclaimer is prepended."""
    from api.chat import _inject_no_sources_disclaimer

    response_text = "According to Federal Decree-Law No. 50 of 2022..."
    result = _inject_no_sources_disclaimer(response_text, sources_found=3)
    assert result == response_text, \
        f"Response should be unchanged when sources found, got: {result[:200]}"


def test_disclaimer_contains_expected_text():
    """Disclaimer contains all key phrases."""
    from api.chat import _inject_no_sources_disclaimer, _NO_SOURCES_DISCLAIMER

    result = _inject_no_sources_disclaimer("Some LLM answer.", sources_found=0)
    assert "⚠️" in result
    assert "knowledge base" in result
    assert "general knowledge" in result
    assert "verify" in result.lower() or "official sources" in result


def test_disclaimer_with_one_source_is_clean():
    """With exactly 1 source found, no disclaimer is prepended."""
    from api.chat import _inject_no_sources_disclaimer

    text = "This is the answer."
    result = _inject_no_sources_disclaimer(text, sources_found=1)
    assert result == text


def test_disclaimer_is_prepended_not_appended():
    """Disclaimer must come before the LLM response text."""
    from api.chat import _inject_no_sources_disclaimer

    response_text = "Some answer."
    result = _inject_no_sources_disclaimer(response_text, sources_found=0)
    assert result.index("⚠️") < result.index(response_text), \
        "Disclaimer should appear before the response text"
