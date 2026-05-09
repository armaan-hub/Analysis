import pytest
from unittest.mock import patch, MagicMock

def test_graph_context_appended_when_available():
    """When graphify is available, _build_graph_context returns non-empty string."""
    from api.chat import _build_graph_context
    mock_result = MagicMock()
    mock_result.label = "VAT Registration"
    mock_result.source_file = "VAT_Guide.pdf"
    with patch("api.chat._graphify_retriever") as mock_gr:
        mock_gr.is_available.return_value = True
        mock_gr.search.return_value = [mock_result, mock_result]
        ctx = _build_graph_context("What is VAT registration?")
    assert "Knowledge Graph Context" in ctx
    assert "VAT Registration" in ctx

def test_graph_skipped_when_not_available():
    """When graphify is unavailable, _build_graph_context returns empty string."""
    from api.chat import _build_graph_context
    with patch("api.chat._graphify_retriever") as mock_gr:
        mock_gr.is_available.return_value = False
        ctx = _build_graph_context("any query")
    assert ctx == ""

def test_graph_exception_returns_empty():
    """When graphify raises an exception, gracefully return empty string."""
    from api.chat import _build_graph_context
    with patch("api.chat._graphify_retriever") as mock_gr:
        mock_gr.is_available.return_value = True
        mock_gr.search.side_effect = RuntimeError("Graph error")
        ctx = _build_graph_context("any query")
    assert ctx == ""
