"""Risk-only baselines for SignalGate Gate G1.

Implements:
- B1: Fixed risk threshold selected on validation partition.
- B2: Risk-only top-budget ranking with deterministic tie handling.
  Primary budget: 1.5x training fraud prevalence.
  Budget sweep: 1.0x, 1.5x, 2.0x, 3.0x training fraud prevalence.

Excludes isFraud from features; uses it only as target / evaluation benchmark.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import average_precision_score


@dataclass(frozen=True)
class TriageMetrics:
    """Quantitative triage evaluation metrics."""

    total_cases: int
    total_fraud: int
    reviewed_cases: int
    touched_rate: float
    detected_fraud: int
    missed_fraud: int
    recall: float
    precision: float
    pr_auc: float


def compute_triage_metrics(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    scores: np.ndarray | None = None,
) -> TriageMetrics:
    """Calculate audit metrics with safe zero-division handling."""
    y_true = np.asarray(y_true, dtype=np.int32)
    y_pred = np.asarray(y_pred, dtype=np.int32)

    total_cases = len(y_true)
    total_fraud = int(np.sum(y_true == 1))
    reviewed_cases = int(np.sum(y_pred == 1))

    touched_rate = float(reviewed_cases / total_cases) if total_cases > 0 else 0.0
    detected_fraud = int(np.sum((y_pred == 1) & (y_true == 1)))
    missed_fraud = int(np.sum((y_pred == 0) & (y_true == 1)))

    recall = float(detected_fraud / total_fraud) if total_fraud > 0 else 0.0
    precision = float(detected_fraud / reviewed_cases) if reviewed_cases > 0 else 0.0

    if scores is not None and len(np.unique(y_true)) > 1:
        pr_auc = float(average_precision_score(y_true, scores))
    else:
        pr_auc = 0.0

    return TriageMetrics(
        total_cases=total_cases,
        total_fraud=total_fraud,
        reviewed_cases=reviewed_cases,
        touched_rate=touched_rate,
        detected_fraud=detected_fraud,
        missed_fraud=missed_fraud,
        recall=recall,
        precision=precision,
        pr_auc=pr_auc,
    )


class RiskEstimator:
    """Deterministic scikit-learn risk model trained strictly on the train partition."""

    def __init__(self, random_state: int = 11, max_iter: int = 50):
        self.random_state = random_state
        self.max_iter = max_iter
        self.clf = HistGradientBoostingClassifier(
            max_iter=self.max_iter,
            random_state=self.random_state,
            class_weight="balanced",
            early_stopping=False,
        )
        self.is_fitted = False

    def fit(self, X_train: np.ndarray, y_train: np.ndarray) -> "RiskEstimator":
        self.clf.fit(X_train, y_train)
        self.is_fitted = True
        return self

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        if not self.is_fitted:
            raise RuntimeError("RiskEstimator must be fitted before predict_proba")
        return self.clf.predict_proba(X)[:, 1]


class FixedThresholdBaseline:
    """Baseline B1: Fixed probability threshold selected using validation only."""

    def __init__(self, threshold: float = 0.5):
        self.threshold = threshold

    def select_threshold_on_validation(
        self,
        y_val_true: np.ndarray,
        val_scores: np.ndarray,
        target_touched_rate: float,
    ) -> float:
        """Select threshold on validation partition that matches target review capacity."""
        # Quantile threshold matching target touched rate
        q = max(0.0, min(1.0, 1.0 - target_touched_rate))
        self.threshold = float(np.quantile(val_scores, q))
        return self.threshold

    def route(self, scores: np.ndarray) -> np.ndarray:
        """Return binary routing decisions: 1 = review queue, 0 = routine."""
        return (scores >= self.threshold).astype(np.int32)


class TopBudgetBaseline:
    """Baseline B2: Risk-only top-budget ranking with deterministic tie handling."""

    def __init__(self, budget_multiple: float = 1.5):
        self.budget_multiple = budget_multiple

    def route(
        self,
        scores: np.ndarray,
        transaction_ids: np.ndarray,
        train_prevalence: float,
    ) -> np.ndarray:
        """Rank transactions by risk and select top budget with deterministic tie handling."""
        n = len(scores)
        if n == 0:
            return np.empty(0, dtype=np.int32)

        budget_rate = self.budget_multiple * train_prevalence
        k = int(np.floor(budget_rate * n))
        k = max(0, min(n, k))

        # Deterministic ranking:
        # Primary sort: scores descending (negative score for ascending sort)
        # Secondary sort: transaction_ids ascending
        order = np.lexsort((transaction_ids, -scores))

        predictions = np.zeros(n, dtype=np.int32)
        if k > 0:
            selected_indices = order[:k]
            predictions[selected_indices] = 1

        return predictions
