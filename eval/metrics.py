"""Evaluation metrics and quantitative audit suite for SignalGate Gate G5.

Implements all required statistical, classification, workload, and calibration
metrics defined in the SignalGate project specification and evidence audit.

Workload Invariant:
  Official workload = (FRAUD_ALERT + MANUAL_REVIEW) / N
  HELD and DEFERRED are reported separately; never counted as reviewed or routine.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any
import numpy as np
from pydantic import BaseModel, ConfigDict, Field
from sklearn.metrics import average_precision_score, brier_score_loss


@dataclass(frozen=True)
class ReliabilityBin:
    """Audit metrics for a single calibration confidence bin."""

    bin_index: int
    bin_lower: float
    bin_upper: float
    sample_count: int
    mean_predicted: float
    observed_frequency: float
    absolute_error: float


class ComprehensiveEvaluationMetrics(BaseModel):
    """Complete quantitative evaluation record for a triage policy."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    total_cases: int = Field(ge=0)
    total_fraud: int = Field(ge=0)
    total_non_fraud: int = Field(ge=0)
    prevalence: float = Field(ge=0.0, le=1.0)

    # Workload and Decisions
    reviewed_cases: int = Field(ge=0)
    official_touched_rate: float = Field(ge=0.0, le=1.0)

    # Primary Classification Metrics
    detected_fraud: int = Field(ge=0)
    missed_fraud: int = Field(ge=0)
    recall: float = Field(ge=0.0, le=1.0)
    missed_fraud_rate: float = Field(ge=0.0, le=1.0)
    precision: float = Field(ge=0.0, le=1.0)
    false_positives: int = Field(ge=0)
    false_positive_rate: float = Field(ge=0.0, le=1.0)
    pr_auc: float = Field(ge=0.0, le=1.0)

    # Routing Lane Distribution
    fraud_alert_count: int = Field(ge=0)
    fraud_alert_rate: float = Field(ge=0.0, le=1.0)
    manual_review_count: int = Field(ge=0)
    manual_review_rate: float = Field(ge=0.0, le=1.0)
    routine_count: int = Field(ge=0)
    routine_rate: float = Field(ge=0.0, le=1.0)
    held_deferred_count: int = Field(ge=0)
    held_deferred_rate: float = Field(ge=0.0, le=1.0)

    # Confident Misses & Queue Safety
    confident_misses: int = Field(ge=0)
    confident_miss_rate: float = Field(ge=0.0, le=1.0)
    queue_overflow_count: int = Field(ge=0)

    # Calibration Diagnostics
    brier_score: float | None = None
    ece: float | None = None


def compute_calibration_ece(
    y_true: np.ndarray,
    probs: np.ndarray,
    n_bins: int = 10,
) -> tuple[float, list[dict[str, Any]]]:
    """Compute Expected Calibration Error (ECE) and binned reliability data.

    ECE = sum_b (N_b / N) * |acc(b) - conf(b)|
    """
    y = np.asarray(y_true, dtype=np.int32)
    p = np.asarray(probs, dtype=np.float64)

    mask = np.isfinite(p) & np.isfinite(y)
    y = y[mask]
    p = p[mask]

    n = len(y)
    if n == 0:
        return 0.0, []

    bin_edges = np.linspace(0.0, 1.0, n_bins + 1)
    ece = 0.0
    bins_data: list[dict[str, Any]] = []

    for i in range(n_bins):
        low, high = bin_edges[i], bin_edges[i + 1]
        if i == n_bins - 1:
            in_bin = (p >= low) & (p <= high)
        else:
            in_bin = (p >= low) & (p < high)

        count = int(np.sum(in_bin))
        if count > 0:
            mean_pred = float(np.mean(p[in_bin]))
            obs_freq = float(np.mean(y[in_bin]))
            abs_err = abs(obs_freq - mean_pred)
            ece += (count / n) * abs_err
        else:
            mean_pred = (low + high) / 2.0
            obs_freq = 0.0
            abs_err = 0.0

        bins_data.append({
            "bin_index": i,
            "bin_lower": round(low, 2),
            "bin_upper": round(high, 2),
            "sample_count": count,
            "mean_predicted": round(mean_pred, 4),
            "observed_frequency": round(obs_freq, 4),
            "absolute_error": round(abs_err, 4),
        })

    return float(ece), bins_data


def compute_comprehensive_metrics(
    y_true: np.ndarray,
    routing_actions: list[str] | np.ndarray,
    risk_scores: np.ndarray | None = None,
    queue_overflow_count: int = 0,
) -> ComprehensiveEvaluationMetrics:
    """Calculate all official audit and evaluation metrics for a triage policy.

    Args:
        y_true: Ground truth binary labels (0 = non-fraud, 1 = fraud).
        routing_actions: Assigned action string for each transaction
                         ('ROUTINE', 'FRAUD_ALERT', 'MANUAL_REVIEW', 'HELD', 'DEFERRED').
                         Alternatively binary array (1 = touched, 0 = routine).
        risk_scores: Continuous calibrated risk scores p in [0, 1].
        queue_overflow_count: Count of transactions that triggered queue capacity limits.

    Returns:
        ComprehensiveEvaluationMetrics model.
    """
    y = np.asarray(y_true, dtype=np.int32)
    n = len(y)

    total_fraud = int(np.sum(y == 1))
    total_non_fraud = n - total_fraud
    prevalence = float(total_fraud / n) if n > 0 else 0.0

    # Parse action strings or binary decisions
    if len(routing_actions) > 0 and isinstance(routing_actions[0], (int, np.integer, bool)):
        # Binary array (1 = touched review, 0 = auto-clear routine)
        decisions_bin = np.asarray(routing_actions, dtype=np.int32)
        fraud_alert_cnt = int(np.sum((decisions_bin == 1) & (risk_scores >= 0.8 if risk_scores is not None else False)))
        manual_review_cnt = int(np.sum(decisions_bin == 1)) - fraud_alert_cnt
        routine_cnt = int(np.sum(decisions_bin == 0))
        held_deferred_cnt = queue_overflow_count
        actions = np.where(decisions_bin == 1, "MANUAL_REVIEW", "ROUTINE")
    else:
        actions = np.asarray(routing_actions, dtype=str)
        fraud_alert_cnt = int(np.sum(actions == "FRAUD_ALERT"))
        manual_review_cnt = int(np.sum(actions == "MANUAL_REVIEW"))
        routine_cnt = int(np.sum(actions == "ROUTINE"))
        held_deferred_cnt = int(np.sum((actions == "HELD") | (actions == "DEFERRED")))

    # Official Workload Formula: (FRAUD_ALERT + MANUAL_REVIEW) / N
    reviewed_cases = fraud_alert_cnt + manual_review_cnt
    touched_rate = float(reviewed_cases / n) if n > 0 else 0.0

    # Classification outcomes
    # Touched cases are those in FRAUD_ALERT or MANUAL_REVIEW
    touched_mask = (actions == "FRAUD_ALERT") | (actions == "MANUAL_REVIEW")
    detected_fraud = int(np.sum(touched_mask & (y == 1)))
    missed_fraud = total_fraud - detected_fraud

    recall = float(detected_fraud / total_fraud) if total_fraud > 0 else 0.0
    missed_fraud_rate = float(missed_fraud / total_fraud) if total_fraud > 0 else 0.0
    precision = float(detected_fraud / reviewed_cases) if reviewed_cases > 0 else 0.0

    false_positives = reviewed_cases - detected_fraud
    false_positive_rate = float(false_positives / total_non_fraud) if total_non_fraud > 0 else 0.0

    # Confident Misses: fraudulent cases explicitly routed to ROUTINE
    routine_mask = (actions == "ROUTINE")
    confident_misses = int(np.sum(routine_mask & (y == 1)))
    confident_miss_rate = float(confident_misses / total_fraud) if total_fraud > 0 else 0.0

    # PR-AUC
    if risk_scores is not None and len(np.unique(y)) > 1:
        pr_auc = float(average_precision_score(y, risk_scores))
    else:
        pr_auc = 0.0

    # Calibration Diagnostics
    brier = None
    ece = None
    if risk_scores is not None:
        p_clean = np.asarray(risk_scores, dtype=np.float64)
        valid = np.isfinite(p_clean) & np.isfinite(y)
        if np.any(valid):
            brier = float(brier_score_loss(y[valid], p_clean[valid]))
            ece_val, _ = compute_calibration_ece(y[valid], p_clean[valid], n_bins=10)
            ece = round(ece_val, 4)

    return ComprehensiveEvaluationMetrics(
        total_cases=n,
        total_fraud=total_fraud,
        total_non_fraud=total_non_fraud,
        prevalence=round(prevalence, 6),
        reviewed_cases=reviewed_cases,
        official_touched_rate=round(touched_rate, 6),
        detected_fraud=detected_fraud,
        missed_fraud=missed_fraud,
        recall=round(recall, 6),
        missed_fraud_rate=round(missed_fraud_rate, 6),
        precision=round(precision, 6),
        false_positives=false_positives,
        false_positive_rate=round(false_positive_rate, 6),
        pr_auc=round(pr_auc, 6),
        fraud_alert_count=fraud_alert_cnt,
        fraud_alert_rate=round(fraud_alert_cnt / n, 6) if n > 0 else 0.0,
        manual_review_count=manual_review_cnt,
        manual_review_rate=round(manual_review_cnt / n, 6) if n > 0 else 0.0,
        routine_count=routine_cnt,
        routine_rate=round(routine_cnt / n, 6) if n > 0 else 0.0,
        held_deferred_count=held_deferred_cnt,
        held_deferred_rate=round(held_deferred_cnt / n, 6) if n > 0 else 0.0,
        confident_misses=confident_misses,
        confident_miss_rate=round(confident_miss_rate, 6),
        queue_overflow_count=queue_overflow_count,
        brier_score=round(brier, 6) if brier is not None else None,
        ece=ece,
    )
