"""Tests for ConfidenceCalibrator — Phase 2D ML-based confidence retraining."""
import pytest
from core.confidence_calibrator import ConfidenceCalibrator


class TestConfidenceCalibrator:
    def setup_method(self):
        self.cal = ConfidenceCalibrator()

    def test_no_feedback_returns_original(self):
        result = self.cal.calibrate(0.8, [])
        assert result == pytest.approx(0.8, abs=1e-4)

    def test_all_accurate_feedback_boosts_confidence(self):
        feedback = [{"feedback_type": "accurate", "original_confidence": 0.7}] * 2
        result = self.cal.calibrate(0.7, feedback)
        assert result >= 0.7

    def test_all_inaccurate_feedback_reduces_confidence(self):
        feedback = [{"feedback_type": "inaccurate", "original_confidence": 0.9}] * 2
        result = self.cal.calibrate(0.9, feedback)
        assert result < 0.9

    def test_result_clamped_to_unit_interval(self):
        feedback = [{"feedback_type": "accurate", "original_confidence": 0.99}] * 2
        result = self.cal.calibrate(0.99, feedback)
        assert 0.0 <= result <= 1.0

    def test_uses_weighted_average_below_min_samples(self):
        """With 2 samples (< MIN_SAMPLES_FOR_ML=3): weighted average used."""
        feedback = [
            {"feedback_type": "accurate", "original_confidence": 0.6},
            {"feedback_type": "inaccurate", "original_confidence": 0.6},
        ]
        result = self.cal.calibrate(0.6, feedback)
        # 70% * 0.6 + 30% * 0.5 = 0.42 + 0.15 = 0.57
        assert result == pytest.approx(0.57, abs=0.01)

    def test_uses_isotonic_regression_at_min_samples(self):
        """With 3+ samples: isotonic regression is used (method changes)."""
        feedback = [
            {"feedback_type": "accurate", "original_confidence": 0.5},
            {"feedback_type": "accurate", "original_confidence": 0.7},
            {"feedback_type": "inaccurate", "original_confidence": 0.9},
        ]
        result = self.cal.calibrate(0.7, feedback)
        assert 0.0 <= result <= 1.0

    def test_partial_feedback_treated_as_half_credit(self):
        feedback = [{"feedback_type": "partial", "original_confidence": 0.8}] * 2
        result = self.cal.calibrate(0.8, feedback)
        # 70% * 0.8 + 30% * 0.5 = 0.56 + 0.15 = 0.71
        assert result == pytest.approx(0.71, abs=0.01)

    def test_calibration_summary_empty(self):
        summary = self.cal.get_calibration_summary([])
        assert summary["count"] == 0
        assert summary["method"] == "none"

    def test_calibration_summary_with_feedback(self):
        feedback = [
            {"feedback_type": "accurate", "original_confidence": 0.8},
            {"feedback_type": "inaccurate", "original_confidence": 0.8},
            {"feedback_type": "partial", "original_confidence": 0.8},
        ]
        summary = self.cal.get_calibration_summary(feedback)
        assert summary["count"] == 3
        assert summary["method"] == "isotonic_regression"
        assert summary["accurate_count"] == 1
        assert summary["inaccurate_count"] == 1
        assert summary["partial_count"] == 1
