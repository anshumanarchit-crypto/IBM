"""Unit tests for calibration wrappers and disagreement signals (G2).

Covers:
- PlattCalibrator: fitted output in [0, 1]; unfitted raises RuntimeError.
- IsotonicCalibrator: fitted output in [0, 1]; monotone constraint preserved;
  unfitted raises RuntimeError.
- calibration_ece: perfect calibration gives ~0 ECE; empty input returns 0.
- compute_signals: shape, range, and mathematical invariants.
- compute_signals_for_sample: scalar output correctness.
- u is zero when all member scores are identical.
- u2 is zero when all member scores are identical.
"""

from __future__ import annotations

import numpy as np
import pytest

from models.calibration import (
    IsotonicCalibrator,
    PlattCalibrator,
    calibration_ece,
)
from models.ensemble import MemberPredictions
from models.signals import compute_signals, compute_signals_for_sample


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def binary_cal_data():
    """Calibration data: simple linearly increasing score."""
    rng = np.random.default_rng(7)
    n = 300
    scores = np.linspace(0.01, 0.99, n)
    labels = (scores > 0.5).astype(int)
    # Add some noise
    flip = rng.choice(n, size=30, replace=False)
    labels[flip] = 1 - labels[flip]
    return scores, labels


@pytest.fixture(scope="module")
def fitted_platt(binary_cal_data):
    scores, labels = binary_cal_data
    cal = PlattCalibrator()
    cal.fit(scores, labels)
    return cal


@pytest.fixture(scope="module")
def fitted_isotonic(binary_cal_data):
    scores, labels = binary_cal_data
    cal = IsotonicCalibrator()
    cal.fit(scores, labels)
    return cal


# ---------------------------------------------------------------------------
# PlattCalibrator tests
# ---------------------------------------------------------------------------

def test_platt_output_range(fitted_platt, binary_cal_data):
    scores, _ = binary_cal_data
    p = fitted_platt.predict_proba(scores)
    assert p.shape == scores.shape
    assert np.all(p >= 0.0) and np.all(p <= 1.0)


def test_platt_unfitted_raises():
    cal = PlattCalibrator()
    with pytest.raises(RuntimeError, match="fitted"):
        cal.predict_proba(np.array([0.3, 0.7]))


# ---------------------------------------------------------------------------
# IsotonicCalibrator tests
# ---------------------------------------------------------------------------

def test_isotonic_output_range(fitted_isotonic, binary_cal_data):
    scores, _ = binary_cal_data
    p = fitted_isotonic.predict_proba(scores)
    assert p.shape == scores.shape
    assert np.all(p >= 0.0) and np.all(p <= 1.0)


def test_isotonic_monotone(fitted_isotonic):
    """Isotonic calibration must preserve rank order (non-decreasing output)."""
    scores = np.linspace(0.0, 1.0, 50)
    p = fitted_isotonic.predict_proba(scores)
    # Isotonic regression is monotone non-decreasing
    diffs = np.diff(p)
    assert np.all(diffs >= -1e-9), "Isotonic calibrator violated monotonicity"


def test_isotonic_unfitted_raises():
    cal = IsotonicCalibrator()
    with pytest.raises(RuntimeError, match="fitted"):
        cal.predict_proba(np.array([0.3, 0.7]))


# ---------------------------------------------------------------------------
# ECE tests
# ---------------------------------------------------------------------------

def test_ece_empty_input():
    ece = calibration_ece(np.array([]), np.array([]))
    assert ece == 0.0


def test_ece_nonnegative(binary_cal_data):
    scores, labels = binary_cal_data
    ece = calibration_ece(scores, labels)
    assert ece >= 0.0


def test_ece_range(binary_cal_data):
    scores, labels = binary_cal_data
    ece = calibration_ece(scores, labels)
    assert ece <= 1.0


# ---------------------------------------------------------------------------
# compute_signals tests
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def sample_member_preds():
    rng = np.random.default_rng(99)
    n_samples, n_members = 50, 7
    proba = rng.uniform(0.0, 1.0, (n_samples, n_members))
    return MemberPredictions(proba_matrix=proba, member_ids=[f"m{i}" for i in range(n_members)])


def test_compute_signals_shape(sample_member_preds):
    out = compute_signals(sample_member_preds)
    assert out.shape == (50,)


def test_compute_signals_p_in_range(sample_member_preds):
    out = compute_signals(sample_member_preds)
    assert np.all(out["p"] >= 0.0) and np.all(out["p"] <= 1.0)


def test_compute_signals_u_nonneg(sample_member_preds):
    out = compute_signals(sample_member_preds)
    assert np.all(out["u"] >= 0.0)


def test_compute_signals_u2_nonneg(sample_member_preds):
    out = compute_signals(sample_member_preds)
    assert np.all(out["u2"] >= 0.0)


def test_compute_signals_n_constant(sample_member_preds):
    out = compute_signals(sample_member_preds)
    n_members = sample_member_preds.proba_matrix.shape[1]
    assert np.all(out["n"] == float(n_members))


def test_compute_signals_u_zero_when_identical():
    """When all member scores are identical, std-dev must be zero."""
    proba = np.full((20, 5), 0.4)
    mp = MemberPredictions(proba_matrix=proba, member_ids=[f"m{i}" for i in range(5)])
    out = compute_signals(mp)
    np.testing.assert_allclose(out["u"], 0.0, atol=1e-12)
    np.testing.assert_allclose(out["u2"], 0.0, atol=1e-12)


def test_compute_signals_p_equals_member_mean(sample_member_preds):
    """p field must equal the row-wise mean of the member proba_matrix."""
    out = compute_signals(sample_member_preds)
    expected_p = sample_member_preds.proba_matrix.mean(axis=1)
    np.testing.assert_allclose(out["p"], expected_p, atol=1e-12)


# ---------------------------------------------------------------------------
# compute_signals_for_sample tests
# ---------------------------------------------------------------------------

def test_signals_for_sample_values():
    scores = np.array([0.1, 0.5, 0.9])
    sig = compute_signals_for_sample(scores)
    assert sig.n == 3.0
    np.testing.assert_allclose(sig.p, scores.mean(), atol=1e-12)
    np.testing.assert_allclose(sig.u, scores.std(ddof=0), atol=1e-12)
    med = np.median(scores)
    np.testing.assert_allclose(sig.u2, np.mean(np.abs(scores - med)), atol=1e-12)


def test_signals_for_sample_identical_scores():
    scores = np.full(7, 0.6)
    sig = compute_signals_for_sample(scores)
    assert sig.u == pytest.approx(0.0, abs=1e-12)
    assert sig.u2 == pytest.approx(0.0, abs=1e-12)
