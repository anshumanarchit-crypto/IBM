"""Probability calibration wrappers for SignalGate Gate G2.

Two calibration strategies are supported:
- Platt / sigmoid scaling (LogisticRegression on raw score)
- Isotonic regression (non-parametric monotone mapping)

Both wrappers are fitted *solely* on the calibration partition.
They receive raw probability scores from a pre-fitted base estimator and
return re-calibrated probabilities on unseen partitions.

Constraints:
- No target labels (isFraud) or raw features enter agent-facing contracts.
- The calibration partition is strictly disjoint from train, validation, test.
"""

from __future__ import annotations

from typing import Literal

import numpy as np
from sklearn.calibration import calibration_curve
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression as _SigmoidFitter

CalibrationMethod = Literal["sigmoid", "isotonic"]


class PlattCalibrator:
    """Platt scaling: logistic regression fit on (raw_score, label) pairs."""

    def __init__(self) -> None:
        self._lr: _SigmoidFitter | None = None
        self.is_fitted = False

    def fit(self, cal_scores: np.ndarray, cal_labels: np.ndarray) -> "PlattCalibrator":
        """Learn sigmoid mapping on calibration partition.

        Args:
            cal_scores: Raw (uncalibrated) probability scores, shape (n,).
            cal_labels: True binary labels, shape (n,). Used only for fitting.
        """
        cal_scores = np.asarray(cal_scores, dtype=np.float64).reshape(-1, 1)
        cal_labels = np.asarray(cal_labels, dtype=np.int32)
        self._lr = _SigmoidFitter(solver="lbfgs", max_iter=1000, C=1.0)
        self._lr.fit(cal_scores, cal_labels)
        self.is_fitted = True
        return self

    def predict_proba(self, scores: np.ndarray) -> np.ndarray:
        """Return Platt-calibrated probabilities, shape (n,)."""
        if not self.is_fitted or self._lr is None:
            raise RuntimeError("PlattCalibrator must be fitted before predict_proba")
        scores = np.asarray(scores, dtype=np.float64).reshape(-1, 1)
        return self._lr.predict_proba(scores)[:, 1]


class IsotonicCalibrator:
    """Isotonic regression calibration: non-parametric monotone mapping."""

    def __init__(self) -> None:
        self._iso: IsotonicRegression | None = None
        self.is_fitted = False

    def fit(self, cal_scores: np.ndarray, cal_labels: np.ndarray) -> "IsotonicCalibrator":
        """Learn isotonic mapping on calibration partition."""
        cal_scores = np.asarray(cal_scores, dtype=np.float64)
        cal_labels = np.asarray(cal_labels, dtype=np.float64)
        self._iso = IsotonicRegression(out_of_bounds="clip")
        self._iso.fit(cal_scores, cal_labels)
        self.is_fitted = True
        return self

    def predict_proba(self, scores: np.ndarray) -> np.ndarray:
        """Return isotonic-calibrated probabilities, clipped to [0, 1]."""
        if not self.is_fitted or self._iso is None:
            raise RuntimeError("IsotonicCalibrator must be fitted before predict_proba")
        scores = np.asarray(scores, dtype=np.float64)
        return np.clip(self._iso.predict(scores), 0.0, 1.0)


def calibration_ece(
    scores: np.ndarray,
    labels: np.ndarray,
    n_bins: int = 10,
) -> float:
    """Expected Calibration Error (ECE) for diagnostic logging only.

    ECE = sum_b (|B_b| / n) * |acc(B_b) - conf(B_b)|

    Not used for tuning or model selection.
    """
    scores = np.asarray(scores, dtype=np.float64)
    labels = np.asarray(labels, dtype=np.int32)
    n = len(scores)
    if n == 0:
        return 0.0

    fraction_of_positives, mean_predicted_value = calibration_curve(
        labels, scores, n_bins=n_bins, strategy="uniform"
    )
    bin_edges = np.linspace(0.0, 1.0, n_bins + 1)
    bin_totals = np.array([
        int(np.sum((scores >= bin_edges[i]) & (scores < bin_edges[i + 1])))
        for i in range(n_bins)
    ])
    k = len(fraction_of_positives)
    bin_weights = bin_totals[:k] / n if n > 0 else np.zeros(k)
    return float(np.sum(bin_weights * np.abs(fraction_of_positives - mean_predicted_value)))
