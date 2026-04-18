"""
ML-based confidence calibrator using isotonic regression on user feedback history.

Calibration logic:
- Collect (original_confidence, is_accurate) pairs from TemplateFeedback
- 'accurate'/'correct' → 1, 'partial' → 0.5, 'inaccurate'/'incorrect' → 0
- If < 3 data points: return weighted average (simple heuristic)
- If >= 3 data points: fit isotonic regression to calibrate
- Clamp result to [0.0, 1.0]
"""
from __future__ import annotations
import numpy as np


class ConfidenceCalibrator:
    """Calibrates template confidence scores using isotonic regression on feedback."""

    MIN_SAMPLES_FOR_ML = 3

    # Supports both "accurate"/"inaccurate" (calibrator-native) and
    # "correct"/"incorrect" (DB-stored legacy values) naming conventions.
    _LABELS: dict[str, float] = {
        "accurate": 1.0,
        "correct": 1.0,
        "partial": 0.5,
        "inaccurate": 0.0,
        "incorrect": 0.0,
    }

    def _label(self, feedback_type: str) -> float:
        return self._LABELS.get(feedback_type, 0.5)

    def _is_accurate(self, ft: str) -> bool:
        return ft in ("accurate", "correct")

    def _is_inaccurate(self, ft: str) -> bool:
        return ft in ("inaccurate", "incorrect")

    def calibrate(
        self,
        original_confidence: float,
        feedback_history: list[dict],
    ) -> float:
        """
        Returns calibrated confidence score in [0.0, 1.0].

        feedback_history items:
            {"feedback_type": "accurate"|"correct"|"inaccurate"|"incorrect"|"partial",
             "original_confidence": float}
        If feedback_history is empty, returns original_confidence unchanged.
        """
        if not feedback_history:
            return float(np.clip(original_confidence, 0.0, 1.0))

        X = np.array([f.get("original_confidence", original_confidence) for f in feedback_history])
        y = np.array([self._label(f["feedback_type"]) for f in feedback_history])

        if len(feedback_history) < self.MIN_SAMPLES_FOR_ML:
            mean_accuracy = float(np.mean(y))
            calibrated = 0.7 * original_confidence + 0.3 * mean_accuracy
            return float(np.clip(calibrated, 0.0, 1.0))

        try:
            from sklearn.isotonic import IsotonicRegression
            order = np.argsort(X)
            X_sorted = X[order]
            y_sorted = y[order]

            ir = IsotonicRegression(out_of_bounds="clip")
            ir.fit(X_sorted, y_sorted)
            calibrated = float(ir.predict([original_confidence])[0])
        except Exception:
            mean_accuracy = float(np.mean(y))
            calibrated = 0.6 * original_confidence + 0.4 * mean_accuracy

        return float(np.clip(calibrated, 0.0, 1.0))

    def get_calibration_summary(self, feedback_history: list[dict]) -> dict:
        """Returns summary stats about the feedback used for calibration."""
        if not feedback_history:
            return {"count": 0, "method": "none", "accuracy_rate": None}

        y = [self._label(f["feedback_type"]) for f in feedback_history]

        return {
            "count": len(feedback_history),
            "method": "isotonic_regression" if len(y) >= self.MIN_SAMPLES_FOR_ML else "weighted_average",
            "accuracy_rate": round(float(np.mean(y)), 4),
            "accurate_count": sum(1 for f in feedback_history if self._is_accurate(f["feedback_type"])),
            "inaccurate_count": sum(1 for f in feedback_history if self._is_inaccurate(f["feedback_type"])),
            "partial_count": sum(1 for f in feedback_history if f["feedback_type"] == "partial"),
        }
