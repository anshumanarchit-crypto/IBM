"""Tests for Gate G5 evaluation harness: metrics, paired bootstrap, and latency."""

import numpy as np
import pandas as pd
import pytest

from eval.bootstrap import BootstrapResult, compute_paired_bootstrap
from eval.latency import LatencyBenchmarkReport, benchmark_latency
from eval.metrics import (
    ComprehensiveEvaluationMetrics,
    compute_calibration_ece,
    compute_comprehensive_metrics,
)


def test_compute_comprehensive_metrics():
    """Verify classification, routing lane, and workload calculations."""
    y_true = np.array([1, 1, 0, 0, 1, 0, 0, 0, 1, 0])
    actions = [
        "FRAUD_ALERT",   # Fraud detected (TP)
        "MANUAL_REVIEW", # Fraud detected (TP)
        "MANUAL_REVIEW", # False positive (FP)
        "ROUTINE",       # True negative (TN)
        "ROUTINE",       # Confident miss (FN)
        "ROUTINE",       # TN
        "ROUTINE",       # TN
        "ROUTINE",       # TN
        "HELD",          # Held/Deferred (FN if positive)
        "ROUTINE",       # TN
    ]
    scores = np.array([0.95, 0.75, 0.65, 0.10, 0.20, 0.05, 0.02, 0.01, 0.50, 0.04])

    m = compute_comprehensive_metrics(y_true, actions, risk_scores=scores)

    assert isinstance(m, ComprehensiveEvaluationMetrics)
    assert m.total_cases == 10
    assert m.total_fraud == 4
    assert m.total_non_fraud == 6
    assert m.prevalence == 0.40

    # Official Workload: (FRAUD_ALERT + MANUAL_REVIEW) / N = (1 + 2) / 10 = 0.30
    assert m.reviewed_cases == 3
    assert m.official_touched_rate == 0.30

    # Detected fraud = cases 0 and 1 = 2
    assert m.detected_fraud == 2
    assert m.missed_fraud == 2
    assert m.recall == 0.50
    assert m.missed_fraud_rate == 0.50

    # Precision = 2 / 3
    assert m.precision == pytest.approx(2 / 3, abs=1e-4)
    # False positives = 1 (case 2)
    assert m.false_positives == 1
    assert m.false_positive_rate == pytest.approx(1 / 6, abs=1e-4)

    # Lanes
    assert m.fraud_alert_count == 1
    assert m.manual_review_count == 2
    assert m.routine_count == 6
    assert m.held_deferred_count == 1

    # Confident Misses: fraud cases routed to ROUTINE (case 4) = 1
    assert m.confident_misses == 1
    assert m.confident_miss_rate == 0.25  # 1 / 4 total fraud

    # Calibration
    assert m.brier_score is not None and m.brier_score >= 0.0
    assert m.ece is not None and 0.0 <= m.ece <= 1.0


def test_calibration_ece_binned():
    """Verify Expected Calibration Error calculation."""
    # Perfectly calibrated predictions
    y = np.array([0, 0, 1, 1, 0, 1, 0, 1, 0, 1])
    p = np.array([0.1, 0.1, 0.9, 0.9, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5])

    ece, bins = compute_calibration_ece(y, p, n_bins=5)
    assert 0.0 <= ece <= 1.0
    assert len(bins) == 5
    assert all("sample_count" in b for b in bins)


def test_paired_bootstrap_identical_policies():
    """When baseline and candidate are identical, delta is zero and CI crosses zero."""
    y = np.array([1, 0, 1, 0, 1, 0, 1, 0, 0, 0])
    scores = np.array([0.9, 0.8, 0.7, 0.6, 0.5, 0.4, 0.3, 0.2, 0.1, 0.05])
    tx_ids = np.arange(10)

    res = compute_paired_bootstrap(
        y, scores, scores, tx_ids, budget_count=4, n_resamples=100, random_seed=42
    )

    assert isinstance(res, BootstrapResult)
    assert res.delta_point_estimate == 0.0
    assert res.bootstrap_mean_delta == pytest.approx(0.0, abs=1e-4)
    assert res.ci_lower <= 0.0 <= res.ci_upper
    assert res.significant_positive is False


def test_paired_bootstrap_superior_candidate():
    """Verify that a candidate correctly prioritizing fraud yields a positive CI."""
    y = np.array([1, 1, 1, 1, 0, 0, 0, 0, 0, 0])
    # Baseline ranks non-fraud high
    scores_base = np.array([0.1, 0.2, 0.3, 0.4, 0.9, 0.8, 0.7, 0.6, 0.5, 0.0])
    # Candidate ranks fraud high
    scores_cand = np.array([0.9, 0.8, 0.7, 0.6, 0.1, 0.2, 0.3, 0.4, 0.5, 0.0])
    tx_ids = np.arange(10)

    res = compute_paired_bootstrap(
        y, scores_base, scores_cand, tx_ids, budget_count=4, n_resamples=200, random_seed=42
    )

    assert res.delta_point_estimate > 0.0
    assert res.ci_lower > 0.0
    assert res.significant_positive is True


def test_benchmark_latency_execution(tmp_path):
    """Test that benchmark_latency produces valid percentiles and verifies AC5."""
    class MockModel:
        def predict_proba(self, X):
            n = len(X)
            probs = np.full((n, 2), 0.5)
            probs[:, 1] = 0.8
            return probs

    class MockPreprocessor:
        def transform(self, df):
            return np.ones((len(df), 10))

    df = pd.DataFrame({"col": np.arange(50)})
    audit_file = tmp_path / "bench_audit.jsonl"

    report = benchmark_latency(
        MockModel(),
        MockPreprocessor(),
        df,
        n_single=20,
        n_batch=10,
        warmup=5,
        audit_log_path=audit_file,
    )

    assert isinstance(report, LatencyBenchmarkReport)
    assert report.single_row_p50_ms <= report.single_row_p95_ms <= report.single_row_p99_ms
    assert report.batch32_p50_ms <= report.batch32_p95_ms <= report.batch32_p99_ms
    assert report.single_row_p95_ms <= report.ac5_target_p95_ms
    assert report.ac5_passed is True
