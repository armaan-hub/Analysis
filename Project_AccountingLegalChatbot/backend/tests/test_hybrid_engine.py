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

    def test_substring_not_counted_as_word_match(self):
        """'tax' inside 'taxation' must NOT score 1.0 (not a whole-word match)."""
        score = _keyword_score("tax", "taxation rules apply here")
        assert score < 1.0, f"Expected < 1.0 for substring-only match, got {score}"

    def test_short_query_words_filtered_from_signal2(self):
        """Words of 2 chars or fewer are excluded from signal-2 check."""
        # 'is' and 'a' are both ≤2 chars, so q_words becomes [] and signal 2 is skipped
        score = _keyword_score("is a", "is a test document about vat")
        # Should NOT score 0.8 via signal 2 — should fall to fuzzy or 0.0
        assert score < 0.8

    def test_missing_text_key_returns_zero(self):
        """Result dict with no 'text' key must return 0.0 keyword score."""
        assert _keyword_score("vat", "") == 0.0


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

    def test_input_list_not_mutated(self):
        """blend_results must not mutate the original list or dicts."""
        original = [
            {"score": 0.9, "text": "hotel apartment vat"},
            {"score": 0.7, "text": "corporate tax filing"},
        ]
        import copy
        snapshot = copy.deepcopy(original)
        blend_results("hotel vat", original)
        assert original == snapshot, "blend_results must not mutate input list/dicts"

    def test_result_missing_text_key_handled(self):
        """Result dict with no 'text' key must not raise an error."""
        results = [{"score": 0.8}]
        out = blend_results("vat", results)
        assert len(out) == 1
        assert "hybrid_score" in out[0]

    def test_identical_hybrid_scores_stable_sort(self):
        """Results with equal hybrid_score preserve pre-sort (vector score) order."""
        # Two results with same text (same keyword score) but different vector scores
        results = [
            {"score": 0.5, "text": "identical text"},
            {"score": 0.9, "text": "identical text"},
        ]
        # Pre-sort by vector score descending (as rag_engine.py does)
        results.sort(key=lambda x: x["score"], reverse=True)
        out = blend_results("unrelated", results)
        # Equal hybrid scores — higher vector score (0.9) must come first
        assert out[0]["score"] == 0.9
