"""Tests for relevance-first RAG: score threshold + default category filter."""
import pytest
from config import settings


def test_rag_min_score_default():
    """rag_min_score must exist and default to 0.45."""
    assert hasattr(settings, "rag_min_score")
    assert 0.0 < settings.rag_min_score < 1.0
    assert settings.rag_min_score == pytest.approx(0.45)
