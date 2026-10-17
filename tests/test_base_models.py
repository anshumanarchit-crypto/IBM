"""Tests for base model interfaces, calibration governance, signal lifecycle, and era assignment (G2).

Covers:
- Base model fitting on training data (HGBC, LR).
- Strict rejection of fitting base models on validation or test.
- Calibrator fitting on calibration data (Platt, Isotonic).
- Strict rejection of fitting calibrators on validation or test.
- Calibrated probability finite bounds [0, 1].
- Chronological era computation using training rows only.
- Signal status tracking ('unfitted', 'ok', 'skipped', 'failed').
- Signal fitting partition guard (rejects validation and test).
- Spearman rank correlation.
- Paired bootstrap recall difference calculation and reproducibility.
"""

from __future__ import annotations

import numpy as np
import pytest

from models.base import (
    brier_score,
    calibrated_p,
    fit_base,
    fit_calibrator,
    raw_score,
    validate_fit_partition,
)
from models.ensemble import (
    compute_training_eras,
    get_era_omitted_indices,
    EraBaggedHeterogeneousEnsemble,
)
from models.signals import (
    BaseSignal,
    DisagreementSignalExtractor,
    RobustDisagreementSignalExtractor,
    paired_bootstrap_recall_difference,
    spearman_rank_correlation,
)


@pytest.fixture(scope="module")
def synthetic_data():
    rng = np.random.default_rng(42)
    n, d = 150, 10
    X = rng.standard_normal((n, d)).astype(np.float32)
    y = rng.integers(0, 2, size=n)
    return X, y


def test_fit_base_hgbc(synthetic_data):
    X, y = synthetic_data
    clf = fit_base("hgbc", X, y, partition="train", max_iter=10)
    scores = raw_score(clf, X)
    assert scores.shape == (len(X),)
    assert np.all(scores >= 0.0) and np.all(scores <= 1.0)


def test_fit_base_lr(synthetic_data):
    X, y = synthetic_data
    pipe = fit_base("lr", X, y, partition="train", max_iter=100)
    scores = raw_score(pipe, X)
    assert scores.shape == (len(X),)
    assert np.all(scores >= 0.0) and np.all(scores <= 1.0)


def test_fit_base_prohibits_validation_and_test(synthetic_data):
    X, y = synthetic_data
    with pytest.raises(ValueError, match="Prohibited partition"):
        fit_base("hgbc", X, y, partition="validation")
    with pytest.raises(ValueError, match="Prohibited partition"):
        fit_base("hgbc", X, y, partition="test")


def test_fit_calibrator_platt_and_isotonic(synthetic_data):
    X, y = synthetic_data
    clf = fit_base("hgbc", X, y, partition="train", max_iter=10)
    scores = raw_score(clf, X)

    cal_platt = fit_calibrator("platt", scores, y, partition="calibration")
    p_platt = calibrated_p(cal_platt, scores)
    assert np.all(p_platt >= 0.0) and np.all(p_platt <= 1.0)
    assert np.all(np.isfinite(p_platt))

    cal_iso = fit_calibrator("isotonic", scores, y, partition="calibration")
    p_iso = calibrated_p(cal_iso, scores)
    assert np.all(p_iso >= 0.0) and np.all(p_iso <= 1.0)
    assert np.all(np.isfinite(p_iso))


def test_fit_calibrator_prohibits_validation_and_test():
    scores = np.array([0.2, 0.8])
    labels = np.array([0, 1])
    with pytest.raises(ValueError, match="Prohibited partition"):
        fit_calibrator("platt", scores, labels, partition="validation")
    with pytest.raises(ValueError, match="Prohibited partition"):
        fit_calibrator("isotonic", scores, labels, partition="test")


def test_brier_score():
    y = np.array([0, 1, 1, 0])
    s = np.array([0.1, 0.9, 0.8, 0.2])
    b = brier_score(y, s)
    assert b >= 0.0 and b <= 1.0


def test_training_era_partitioning():
    n_train = 1000
    eras = compute_training_eras(n_train, n_eras=5)
    assert len(eras) == 5
    # Total coverage without overlap
    assert eras[0][0] == 0
    assert eras[-1][1] == n_train
    for i in range(len(eras) - 1):
        assert eras[i][1] == eras[i + 1][0]

    # Check era omission
    for era_idx in range(5):
        omitted = get_era_omitted_indices(n_train, omit_era_idx=era_idx, n_eras=5)
        start, end = eras[era_idx]
        expected_len = n_train - (end - start)
        assert len(omitted) == expected_len
        # Ensure omitted indices do not intersect omitted era
        assert not np.any((omitted >= start) & (omitted < end))


def test_signal_status_lifecycle(synthetic_data):
    X, y = synthetic_data
    extractor = DisagreementSignalExtractor()
    assert extractor.status == "unfitted"

    # Permitted fit
    extractor.fit(partition="train", X=X, y=y)
    assert extractor.status == "ok"

    # Prohibited fit
    with pytest.raises(ValueError, match="Prohibited partition"):
        extractor.fit(partition="validation", X=X, y=y)

    with pytest.raises(ValueError, match="Prohibited partition"):
        extractor.fit(partition="test", X=X, y=y)

    # Permitted skip
    extractor.skip("Test skip reason")
    assert extractor.status == "skipped"


def test_spearman_rank_correlation():
    x = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
    y = np.array([2.0, 4.0, 6.0, 8.0, 10.0])
    corr = spearman_rank_correlation(x, y)
    assert corr == pytest.approx(1.0, abs=1e-5)

    y_inv = np.array([10.0, 8.0, 6.0, 4.0, 2.0])
    corr_inv = spearman_rank_correlation(x, y_inv)
    assert corr_inv == pytest.approx(-1.0, abs=1e-5)


def test_paired_bootstrap_reproducibility():
    rng = np.random.default_rng(123)
    n = 200
    y_true = rng.integers(0, 2, size=n)
    s_base = rng.uniform(0, 1, size=n)
    s_cand = s_base.copy()  # identical scores -> zero delta

    res1 = paired_bootstrap_recall_difference(y_true, s_base, s_cand, budget_count=20, n_resamples=100, random_state=11)
    res2 = paired_bootstrap_recall_difference(y_true, s_base, s_cand, budget_count=20, n_resamples=100, random_state=11)

    assert res1["delta_mean"] == pytest.approx(0.0, abs=1e-10)
    assert res1["ci_lower"] == pytest.approx(0.0, abs=1e-10)
    assert res1["ci_upper"] == pytest.approx(0.0, abs=1e-10)
    assert res1["significant_positive"] is False
    assert res1 == res2
