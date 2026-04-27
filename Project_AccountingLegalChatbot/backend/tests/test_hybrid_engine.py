"""Tests for the hybrid keyword re-ranking engine."""

import pytest
from core.search.hybrid_engine import blend_results, _keyword_score


class TestKeywordScore:
    def test_exact_phrase_scores_one(self):
        assert _keyword_score("hotel apartment vat", "hotel apartment vat exemption rules") == 1.0

    def test_all_words_present_scores_point_eight(self):
        score = _keyword_score("hotel vat", "the hotel is subject to vat regulations")
        assert score == 0.8

    def test_empty_query_returns_zero(self):
        assert _keyword_score("", "some text") == 0.0

    def test_empty_text_returns_zero(self):
        assert _keyword_score("vat", "") == 0.0

    def test_unrelated_text_scores_below_threshold(self):
        score = _keyword_score("peppol invoice", "labour law termination notice period")
        assert score < 0.5


class TestBlendResults:
    def test_empty_results_returned_unchanged(self):
        assert blend_results("query", []) == []

    def test_hybrid_score_added_to_results(self):
        results = [{"score": 0.9, "text": "vat on hotel apartments"}]
        out = blend_results("hotel apartment vat", results)
        assert "hybrid_score" in out[0]

    def test_results_sorted_by_hybrid_score(self):
        results = [
            {"score": 0.6, "text": "hotel apartment vat treatment in UAE"},  # high keyword
            {"score": 0.9, "text": "corporate tax filing deadlines"},         # high vector, low keyword
        ]
        out = blend_results("hotel apartment vat", results)
        # First result should be the one with better combined score
        assert out[0]["text"] == "hotel apartment vat treatment in UAE" or out[0]["hybrid_score"] >= out[1]["hybrid_score"]

    def test_original_score_preserved(self):
        results = [{"score": 0.75, "text": "some text"}]
        out = blend_results("query", results)
        assert out[0]["score"] == 0.75

    def test_custom_weights_respected(self):
        results = [
            {"score": 1.0, "text": "completely unrelated text about something else"},
            {"score": 0.5, "text": "exact query match here"},
        ]
        out = blend_results("exact query match", results, vector_weight=0.3, keyword_weight=0.7)
        # With high keyword weight, the keyword match should win
        assert out[0]["text"] == "exact query match here"
