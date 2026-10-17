"""Tests for batch drift monitoring (Gate G4)."""

import numpy as np
import pandas as pd
import pytest

from monitoring.drift import (
    BatchDriftReport,
    DriftMonitor,
    FeatureDriftResult,
    calculate_ks,
    calculate_psi,
)


def test_calculate_psi_identical_distributions():
    """Identical distributions should have PSI of 0.0."""
    rng = np.random.RandomState(42)
    data = rng.normal(loc=10.0, scale=2.0, size=1000)

    psi = calculate_psi(data, data)
    assert isinstance(psi, float)
    assert psi == pytest.approx(0.0, abs=1e-4)


def test_calculate_psi_stable_vs_shifted():
    """Verify that stable distributions have low PSI while shifted have high PSI."""
    rng = np.random.RandomState(42)
    ref = rng.normal(loc=0.0, scale=1.0, size=2000)
    stable_curr = rng.normal(loc=0.02, scale=1.01, size=2000)
    shifted_curr = rng.normal(loc=1.5, scale=2.0, size=2000)

    psi_stable = calculate_psi(ref, stable_curr)
    psi_shifted = calculate_psi(ref, shifted_curr)

    assert psi_stable < 0.10, f"Expected stable PSI < 0.10, got {psi_stable}"
    assert psi_shifted >= 0.25, f"Expected shifted PSI >= 0.25, got {psi_shifted}"


def test_calculate_psi_edge_cases():
    """Test constant arrays, NaNs, empty inputs, and single-value columns."""
    # 1. Constant arrays (zero variance)
    const_ref = np.ones(500) * 42.0
    const_curr_same = np.ones(500) * 42.0
    assert calculate_psi(const_ref, const_curr_same) == 0.0

    const_curr_diff = np.ones(500) * 99.0
    psi_diff = calculate_psi(const_ref, const_curr_diff)
    assert psi_diff > 0.0

    # 2. Arrays with NaNs and Infs
    nan_ref = np.array([1.0, 2.0, np.nan, 4.0, np.inf, 5.0])
    nan_curr = np.array([np.nan, 1.0, 2.0, 4.0, 5.0, np.nan])
    psi_nan = calculate_psi(nan_ref, nan_curr)
    assert psi_nan == pytest.approx(0.0, abs=1e-3)

    # 3. Empty arrays
    assert calculate_psi([], []) == 0.0
    assert calculate_psi([1.0, 2.0], []) == 0.0
    assert calculate_psi([], [1.0, 2.0]) == 0.0


def test_calculate_ks_statistic_and_pvalue():
    """Verify KS calculation under identical, shifted, and constant distributions."""
    rng = np.random.RandomState(42)
    ref = rng.normal(loc=0.0, scale=1.0, size=1000)
    curr_same = rng.normal(loc=0.0, scale=1.0, size=1000)
    curr_shift = rng.normal(loc=3.0, scale=1.0, size=1000)

    stat_same, p_same = calculate_ks(ref, curr_same)
    assert 0.0 <= stat_same <= 1.0
    assert p_same > 0.01  # Cannot reject null hypothesis that they are from same distribution

    stat_shift, p_shift = calculate_ks(ref, curr_shift)
    assert stat_shift > 0.5
    assert p_shift < 1e-10  # Highly significant divergence

    # Constant arrays
    stat_c, p_c = calculate_ks(np.zeros(100), np.zeros(100))
    assert stat_c == 0.0 and p_c == 1.0

    stat_c_diff, p_c_diff = calculate_ks(np.zeros(100), np.ones(100))
    assert stat_c_diff == 1.0 and p_c_diff == 0.0


def test_drift_monitor_full_workflow():
    """Verify DriftMonitor evaluation against reference baseline."""
    rng = np.random.RandomState(42)
    ref_df = pd.DataFrame({
        "p": rng.beta(a=0.5, b=10, size=2000),
        "u": rng.exponential(scale=0.05, size=2000),
        "feat_A": rng.normal(loc=100.0, scale=15.0, size=2000),
        "feat_B": np.zeros(2000),  # constant
    })

    monitor = DriftMonitor(reference_data=ref_df, reference_window="train")

    # 1. Stable batch
    stable_batch = pd.DataFrame({
        "p": rng.beta(a=0.5, b=10, size=500),
        "u": rng.exponential(scale=0.05, size=500),
        "feat_A": rng.normal(loc=100.5, scale=14.8, size=500),
        "feat_B": np.zeros(500),
    })
    report_stable = monitor.evaluate_batch(stable_batch, batch_id="batch_stable_01")
    assert isinstance(report_stable, BatchDriftReport)
    assert report_stable.overall_drift_detected is False
    assert len(report_stable.significant_shift_features) == 0
    assert "p" in report_stable.feature_results
    assert report_stable.feature_results["p"].shift_severity == "none"
    assert "fraud prevalence has increased" in report_stable.disclaimer

    # 2. Shifted batch
    shifted_batch = pd.DataFrame({
        "p": rng.beta(a=2.0, b=2.0, size=500),  # Massive risk score drift
        "u": rng.exponential(scale=0.05, size=500),
        "feat_A": rng.normal(loc=180.0, scale=30.0, size=500),  # Severe feature drift
        "feat_B": np.ones(500),  # Shift from 0 to 1
    })
    report_shifted = monitor.evaluate_batch(shifted_batch, batch_id="batch_shifted_01")
    assert report_shifted.overall_drift_detected is True
    assert "p" in report_shifted.significant_shift_features
    assert "feat_A" in report_shifted.significant_shift_features


def test_drift_monitor_empty_batch_and_invalid_inputs():
    """Test that empty batch or invalid types fail cleanly."""
    ref_dict = {"p": np.array([0.1, 0.2, 0.3])}
    monitor = DriftMonitor(reference_data=ref_dict)

    # Empty DataFrame
    empty_report = monitor.evaluate_batch(pd.DataFrame({"p": []}), batch_id="empty_01")
    assert empty_report.sample_size == 0
    assert empty_report.overall_drift_detected is False

    # Invalid input types
    with pytest.raises(TypeError):
        monitor.evaluate_batch("invalid_type")  # type: ignore

    with pytest.raises(TypeError):
        DriftMonitor(reference_data=12345)  # type: ignore
