"""Paired-bootstrap confidence interval evaluation for SignalGate Gate G5.

Implements matched paired-bootstrap resampling to measure statistical significance
of recall differences between candidate triage policies and baselines:

  Delta Recall = Recall_candidate - Recall_baseline

Statistical Protocol:
- 1,000 paired resamples by default.
- Fixed, recorded random seed for strict determinism.
- Matched row resampling across both policies simultaneously.
- Empirical percentile confidence interval [2.5%, 97.5%] for 95% level.
- Statistical significance requires: ci_lower > 0.0 (strictly positive).
"""

from __future__ import annotations

import numpy as np
from pydantic import BaseModel, ConfigDict, Field


class BootstrapResult(BaseModel):
    """Quantitative outcome of a paired bootstrap evaluation."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    metric_name: str = "recall_difference"
    baseline_name: str = Field(min_length=1)
    candidate_name: str = Field(min_length=1)
    sample_size: int = Field(ge=0)
    fraud_count: int = Field(ge=0)
    baseline_point_estimate: float
    candidate_point_estimate: float
    delta_point_estimate: float
    bootstrap_mean_delta: float
    ci_lower: float
    ci_upper: float
    confidence_level: float = 0.95
    n_resamples: int = Field(ge=1)
    random_seed: int
    significant_positive: bool
    interpretation: str


def compute_paired_bootstrap(
    y_true: np.ndarray,
    scores_baseline: np.ndarray,
    scores_candidate: np.ndarray,
    tx_ids: np.ndarray,
    budget_count: int,
    n_resamples: int = 1000,
    random_seed: int = 42,
    confidence_level: float = 0.95,
    baseline_name: str = "B2_RiskOnly",
    candidate_name: str = "P5_Candidate",
) -> BootstrapResult:
    """Execute matched paired-bootstrap resampling for recall difference.

    Args:
        y_true: Ground truth binary fraud labels.
        scores_baseline: Continuous ranking scores for baseline.
        scores_candidate: Continuous ranking scores for candidate.
        tx_ids: Transaction identifiers for deterministic secondary sort.
        budget_count: Exact review capacity k (top-k cases reviewed).
        n_resamples: Number of bootstrap iterations (default: 1000).
        random_seed: PRNG seed for reproducibility.
        confidence_level: Two-sided interval coverage (default: 0.95).
        baseline_name: Descriptive label for baseline policy.
        candidate_name: Descriptive label for candidate policy.

    Returns:
        BootstrapResult with point estimates, confidence intervals, and significance.
    """
    y = np.asarray(y_true, dtype=np.int32)
    s_base = np.asarray(scores_baseline, dtype=np.float64)
    s_cand = np.asarray(scores_candidate, dtype=np.float64)
    ids = np.asarray(tx_ids)
    n = len(y)

    total_positives = int(np.sum(y == 1))
    if n == 0 or total_positives == 0 or budget_count <= 0:
        return BootstrapResult(
            baseline_name=baseline_name,
            candidate_name=candidate_name,
            sample_size=n,
            fraud_count=total_positives,
            baseline_point_estimate=0.0,
            candidate_point_estimate=0.0,
            delta_point_estimate=0.0,
            bootstrap_mean_delta=0.0,
            ci_lower=0.0,
            ci_upper=0.0,
            confidence_level=confidence_level,
            n_resamples=n_resamples,
            random_seed=random_seed,
            significant_positive=False,
            interpretation="Degenerate input (0 cases or 0 positive fraud instances).",
        )

    k = max(0, min(budget_count, n))

    # Point Estimates on full sample
    order_base = np.lexsort((ids, -s_base))
    selected_base = order_base[:k]
    base_point = float(np.sum(y[selected_base] == 1) / total_positives)

    order_cand = np.lexsort((ids, -s_cand))
    selected_cand = order_cand[:k]
    cand_point = float(np.sum(y[selected_cand] == 1) / total_positives)

    delta_point = cand_point - base_point

    # Paired Bootstrap Resampling
    rng = np.random.default_rng(random_seed)
    deltas = np.empty(n_resamples, dtype=np.float64)

    for i in range(n_resamples):
        idx = rng.choice(n, size=n, replace=True)
        y_b = y[idx]
        pos_b = np.sum(y_b == 1)

        if pos_b == 0:
            deltas[i] = 0.0
            continue

        s_b_base = s_base[idx]
        s_b_cand = s_cand[idx]
        ids_b = ids[idx]

        # Baseline selection on resample
        top_b_base = np.argpartition(-s_b_base, k - 1)[:k]
        rec_b_base = np.sum(y_b[top_b_base] == 1) / pos_b

        # Candidate selection on resample
        top_b_cand = np.argpartition(-s_b_cand, k - 1)[:k]
        rec_b_cand = np.sum(y_b[top_b_cand] == 1) / pos_b

        deltas[i] = float(rec_b_cand - rec_b_base)

    alpha = (1.0 - confidence_level) / 2.0
    ci_lower = float(np.percentile(deltas, 100.0 * alpha))
    ci_upper = float(np.percentile(deltas, 100.0 * (1.0 - alpha)))
    mean_delta = float(np.mean(deltas))

    significant = ci_lower > 0.0

    if significant:
        interpretation = (
            f"Statistically significant improvement: Delta Recall = {delta_point * 100:+.2f} pp, "
            f"95% CI [{ci_lower * 100:+.2f} pp, {ci_upper * 100:+.2f} pp] strictly above zero."
        )
    elif ci_upper < 0.0:
        interpretation = (
            f"Statistically significant degradation: Delta Recall = {delta_point * 100:+.2f} pp, "
            f"95% CI [{ci_lower * 100:+.2f} pp, {ci_upper * 100:+.2f} pp] strictly below zero."
        )
    else:
        interpretation = (
            f"No statistically significant difference: Delta Recall = {delta_point * 100:+.2f} pp, "
            f"95% CI [{ci_lower * 100:+.2f} pp, {ci_upper * 100:+.2f} pp] crosses zero."
        )

    return BootstrapResult(
        baseline_name=baseline_name,
        candidate_name=candidate_name,
        sample_size=n,
        fraud_count=total_positives,
        baseline_point_estimate=round(base_point, 6),
        candidate_point_estimate=round(cand_point, 6),
        delta_point_estimate=round(delta_point, 6),
        bootstrap_mean_delta=round(mean_delta, 6),
        ci_lower=round(ci_lower, 6),
        ci_upper=round(ci_upper, 6),
        confidence_level=confidence_level,
        n_resamples=n_resamples,
        random_seed=random_seed,
        significant_positive=significant,
        interpretation=interpretation,
    )
