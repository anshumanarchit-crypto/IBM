"""Tests for feature leakage prevention, deterministic ranking, and metric handling."""

import numpy as np
import pandas as pd
import pytest

from models.features import FeaturePipeline, FORBIDDEN_INPUT_COLUMNS
from models.baselines import (
    TopBudgetBaseline,
    FixedThresholdBaseline,
    compute_triage_metrics,
)


@pytest.fixture
def mock_dataset() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Create train and test mock dataframes."""
    n_train = 500
    n_test = 200
    train_df = pd.DataFrame({
        "TransactionID": np.arange(1, n_train + 1),
        "TransactionDT": np.arange(100, 100 + n_train * 5, 5),
        "isFraud": np.random.binomial(1, 0.04, n_train),
        "TransactionAmt": np.random.exponential(100, n_train),
        "ProductCD": np.random.choice(["W", "C", "R", "H"], n_train),
        "card1": np.random.randint(1000, 9999, n_train),
        "C1": np.random.poisson(2, n_train),
    })

    test_df = pd.DataFrame({
        "TransactionID": np.arange(n_train + 1, n_train + n_test + 1),
        "TransactionDT": np.arange(5000, 5000 + n_test * 5, 5),
        "isFraud": np.random.binomial(1, 0.04, n_test),
        "TransactionAmt": np.random.exponential(100, n_test),
        "ProductCD": np.random.choice(["W", "C", "R", "H", "NEW"], n_test),  # includes unseen category
        "card1": np.random.randint(1000, 9999, n_test),
        "C1": np.random.poisson(2, n_test),
    })
    return train_df, test_df


def test_feature_pipeline_excludes_forbidden_columns(mock_dataset):
    train_df, test_df = mock_dataset
    pipeline = FeaturePipeline()
    pipeline.fit(train_df)
    manifest = pipeline.get_manifest()

    # Invariant: isFraud, TransactionID, TransactionDT must NEVER be features
    for col in FORBIDDEN_INPUT_COLUMNS:
        assert col not in manifest.feature_names, f"Forbidden column {col} found in feature manifest!"
        assert col in manifest.excluded_columns

    X_train = pipeline.transform(train_df)
    X_test = pipeline.transform(test_df)
    assert X_train.shape[1] == manifest.feature_count
    assert X_test.shape[1] == manifest.feature_count
    assert not np.isnan(X_test).any(), "Unseen categories caused unhandled NaNs in X_test!"


def test_deterministic_tie_breaking():
    """Verify that when predicted risk scores are tied, tie-breaking is deterministic."""
    scores = np.array([0.8, 0.8, 0.8, 0.2, 0.1])
    # Different TransactionIDs
    tx_ids = np.array([5003, 5001, 5002, 5004, 5005])

    b2 = TopBudgetBaseline(budget_multiple=1.0)
    # Target 2 cases
    train_prev = 0.4  # 0.4 * 5 = 2 cases

    preds1 = b2.route(scores, tx_ids, train_prev)
    preds2 = b2.route(scores, tx_ids, train_prev)

    assert np.array_equal(preds1, preds2), "Tie-breaking is not deterministic across runs!"
    # Lowest TransactionID among tied 0.8 scores should win: 5001 (idx 1) and 5002 (idx 2)
    assert preds1[1] == 1, "TransactionID 5001 should be prioritized by tie-breaker"
    assert preds1[2] == 1, "TransactionID 5002 should be prioritized by tie-breaker"
    assert preds1[0] == 0, "TransactionID 5003 should be excluded in tie-break for top-2"


def test_touched_rate_honors_budget():
    """Verify top-budget touched rate matches floor(multiple * prev * n) / n."""
    n = 10000
    scores = np.random.uniform(0.0, 1.0, n)
    tx_ids = np.arange(n)
    train_prev = 0.035  # 3.5%

    for mult in [1.0, 1.5, 2.0, 3.0]:
        b2 = TopBudgetBaseline(budget_multiple=mult)
        preds = b2.route(scores, tx_ids, train_prev)
        expected_k = int(np.floor(mult * train_prev * n))
        actual_reviewed = int(np.sum(preds))
        assert actual_reviewed == expected_k
        assert np.isclose(actual_reviewed / n, expected_k / n)


def test_rare_class_metric_handling():
    """Verify metric computation gracefully handles zero fraud and zero predictions."""
    # Zero fraud in partition
    y_true_zero = np.zeros(100, dtype=int)
    y_pred = np.zeros(100, dtype=int)
    y_pred[:5] = 1

    m1 = compute_triage_metrics(y_true_zero, y_pred, np.random.uniform(0, 1, 100))
    assert m1.total_fraud == 0
    assert m1.recall == 0.0
    assert m1.precision == 0.0
    assert m1.pr_auc == 0.0

    # Zero reviewed
    y_true = np.array([0, 1, 0, 1])
    y_pred_zero = np.zeros(4, dtype=int)
    m2 = compute_triage_metrics(y_true, y_pred_zero)
    assert m2.reviewed_cases == 0
    assert m2.recall == 0.0
    assert m2.precision == 0.0
    assert m2.detected_fraud == 0
    assert m2.missed_fraud == 2


def test_fixed_threshold_baseline_routing():
    b1 = FixedThresholdBaseline(threshold=0.7)
    scores = np.array([0.9, 0.7, 0.69, 0.1])
    preds = b1.route(scores)
    assert np.array_equal(preds, [1, 1, 0, 0])
