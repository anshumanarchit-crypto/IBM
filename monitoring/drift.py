"""Batch-level drift monitoring for SignalGate (Gate G4).

Provides Population Stability Index (PSI) and Kolmogorov-Smirnov (KS) diagnostics
for permitted transaction features and model score distributions.

Statistical Invariants & Design Principles:
1. Deterministic calculations with documented, immutable reference distributions.
2. Safe handling of missing values, zero-variance (constant) features, and empty batches.
3. Machine-readable typed reports.
4. Explicit semantic distinction: Distribution shift measures covariate or score drift;
   it DOES NOT constitute proof or evidence of increased fraud prevalence.
5. Batch diagnostics operate strictly as monitoring signals, NEVER as an unregistered
   substitute for transaction-level triage routing.
"""

from __future__ import annotations

from datetime import datetime, timezone
import math
from typing import Any, Literal
import numpy as np
import pandas as pd
from pydantic import BaseModel, ConfigDict, Field
from scipy import stats

ShiftSeverity = Literal["none", "moderate", "significant"]

PSI_STABLE_THRESHOLD = 0.10
PSI_SIGNIFICANT_THRESHOLD = 0.25
DEFAULT_EPSILON = 1e-4


class FeatureDriftResult(BaseModel):
    """Diagnostic drift metrics for a single monitored feature."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    feature_name: str = Field(min_length=1)
    psi: float = Field(ge=0.0)
    ks_statistic: float = Field(ge=0.0, le=1.0)
    p_value: float = Field(ge=0.0, le=1.0)
    reference_count: int = Field(ge=0)
    current_count: int = Field(ge=0)
    reference_mean: float | None = None
    current_mean: float | None = None
    reference_std: float | None = None
    current_std: float | None = None
    missing_count_current: int = Field(ge=0)
    missing_rate_current: float = Field(ge=0.0, le=1.0)
    shift_severity: ShiftSeverity
    drift_detected: bool
    interpretation: str


class BatchDriftReport(BaseModel):
    """Comprehensive machine-readable drift audit for a transaction batch."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    batch_id: str = Field(min_length=1)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    reference_window: str = Field(min_length=1)
    sample_size: int = Field(ge=0)
    features_monitored: list[str]
    feature_results: dict[str, FeatureDriftResult]
    overall_drift_detected: bool
    significant_shift_features: list[str]
    moderate_shift_features: list[str]
    summary: str
    disclaimer: str = (
        "Statistical distribution shift indicates a change in feature or score distributions "
        "relative to the reference period. It does NOT constitute proof or evidence that "
        "fraud prevalence has increased."
    )


def calculate_psi(
    reference: np.ndarray | list[float],
    current: np.ndarray | list[float],
    num_bins: int = 10,
    epsilon: float = DEFAULT_EPSILON,
) -> float:
    """Calculate Population Stability Index (PSI) with robust edge-case handling.

    Args:
        reference: Reference baseline array.
        current: Current batch array.
        num_bins: Target number of quantile bins (default: 10).
        epsilon: Laplace smoothing term to prevent log(0) or division by zero.

    Returns:
        PSI metric (float >= 0.0).
    """
    ref = np.asarray(reference, dtype=np.float64)
    curr = np.asarray(current, dtype=np.float64)

    # Filter out NaNs and non-finite values
    ref = ref[np.isfinite(ref)]
    curr = curr[np.isfinite(curr)]

    if len(ref) == 0 or len(curr) == 0:
        return 0.0

    # Constant feature handling
    ref_min, ref_max = float(np.min(ref)), float(np.max(ref))
    curr_min, curr_max = float(np.min(curr)), float(np.max(curr))

    if ref_min == ref_max:
        if curr_min == curr_max and ref_min == curr_min:
            return 0.0
        # If reference is constant but current has shifted
        # Create 2 bins: [ref_min, ref_min] and everything else
        ref_in = np.sum(ref == ref_min)
        curr_in = np.sum(curr == ref_min)
        p_in = (curr_in + epsilon) / (len(curr) + 2 * epsilon)
        q_in = (ref_in + epsilon) / (len(ref) + 2 * epsilon)
        p_out = (len(curr) - curr_in + epsilon) / (len(curr) + 2 * epsilon)
        q_out = (len(ref) - ref_in + epsilon) / (len(ref) + 2 * epsilon)
        return float((p_in - q_in) * np.log(p_in / q_in) + (p_out - q_out) * np.log(p_out / q_out))

    # Quantile-based bin edges on reference distribution
    quantiles = np.linspace(0.0, 1.0, num_bins + 1)
    raw_edges = np.quantile(ref, quantiles)
    # Deduplicate edges if quantiles collapse
    bin_edges = np.unique(raw_edges)

    if len(bin_edges) < 2:
        return 0.0

    # Ensure outermost boundaries cover extremes of both distributions
    bin_edges[0] = min(bin_edges[0], curr_min) - 1e-6
    bin_edges[-1] = max(bin_edges[-1], curr_max) + 1e-6

    # Histogram counts
    ref_counts, _ = np.histogram(ref, bins=bin_edges)
    curr_counts, _ = np.histogram(curr, bins=bin_edges)

    k = len(ref_counts)
    # Laplace-smoothed empirical distributions
    ref_dist = (ref_counts + epsilon) / (len(ref) + k * epsilon)
    curr_dist = (curr_counts + epsilon) / (len(curr) + k * epsilon)

    psi_val = np.sum((curr_dist - ref_dist) * np.log(curr_dist / ref_dist))
    return float(max(0.0, psi_val))


def calculate_ks(
    reference: np.ndarray | list[float],
    current: np.ndarray | list[float],
) -> tuple[float, float]:
    """Calculate Two-Sample Kolmogorov-Smirnov statistic and asymptotic p-value.

    Returns:
        (ks_statistic, p_value)
    """
    ref = np.asarray(reference, dtype=np.float64)
    curr = np.asarray(current, dtype=np.float64)

    ref = ref[np.isfinite(ref)]
    curr = curr[np.isfinite(curr)]

    if len(ref) == 0 or len(curr) == 0:
        return (0.0, 1.0)

    # Constant feature handling
    if np.all(ref == ref[0]) and np.all(curr == curr[0]):
        if ref[0] == curr[0]:
            return (0.0, 1.0)
        return (1.0, 0.0)

    res = stats.ks_2samp(ref, curr)
    stat = float(res.statistic)
    p_val = float(res.pvalue)

    # Sanitize p_value bounds
    p_val = max(0.0, min(1.0, p_val))
    stat = max(0.0, min(1.0, stat))
    return (stat, p_val)


class DriftMonitor:
    """Batch-level drift diagnostic engine."""

    def __init__(
        self,
        reference_data: dict[str, np.ndarray | list[float]] | pd.DataFrame,
        reference_window: str = "train",
        psi_moderate_threshold: float = PSI_STABLE_THRESHOLD,
        psi_significant_threshold: float = PSI_SIGNIFICANT_THRESHOLD,
    ) -> None:
        self.reference_window = reference_window
        self.psi_mod_th = psi_moderate_threshold
        self.psi_sig_th = psi_significant_threshold

        self.reference_features: dict[str, np.ndarray] = {}
        if isinstance(reference_data, pd.DataFrame):
            for col in reference_data.columns:
                vals = reference_data[col].to_numpy(dtype=np.float64)
                self.reference_features[col] = vals
        elif isinstance(reference_data, dict):
            for k, v in reference_data.items():
                self.reference_features[k] = np.asarray(v, dtype=np.float64)
        else:
            raise TypeError("reference_data must be a pandas DataFrame or dict of arrays")

    def evaluate_batch(
        self,
        current_data: dict[str, np.ndarray | list[float]] | pd.DataFrame,
        batch_id: str = "batch_001",
    ) -> BatchDriftReport:
        """Evaluate a transaction batch against the baseline reference."""
        if isinstance(current_data, pd.DataFrame):
            curr_dict: dict[str, np.ndarray] = {
                c: current_data[c].to_numpy(dtype=np.float64) for c in current_data.columns
            }
            batch_len = len(current_data)
        elif isinstance(current_data, dict):
            curr_dict = {k: np.asarray(v, dtype=np.float64) for k, v in current_data.items()}
            batch_len = max((len(v) for v in curr_dict.values()), default=0)
        else:
            raise TypeError("current_data must be a pandas DataFrame or dict of arrays")

        if batch_len == 0:
            return BatchDriftReport(
                batch_id=batch_id,
                reference_window=self.reference_window,
                sample_size=0,
                features_monitored=list(self.reference_features.keys()),
                feature_results={},
                overall_drift_detected=False,
                significant_shift_features=[],
                moderate_shift_features=[],
                summary="Empty batch: zero records evaluated.",
            )

        feature_results: dict[str, FeatureDriftResult] = {}
        significant_shifts: list[str] = []
        moderate_shifts: list[str] = []

        for feat_name, ref_arr in self.reference_features.items():
            if feat_name not in curr_dict:
                continue

            curr_arr = curr_dict[feat_name]
            total_curr = len(curr_arr)
            valid_curr = curr_arr[np.isfinite(curr_arr)]
            missing_curr = total_curr - len(valid_curr)
            missing_rate = float(missing_curr / total_curr) if total_curr > 0 else 0.0

            valid_ref = ref_arr[np.isfinite(ref_arr)]

            ref_mean = float(np.mean(valid_ref)) if len(valid_ref) > 0 else None
            curr_mean = float(np.mean(valid_curr)) if len(valid_curr) > 0 else None
            ref_std = float(np.std(valid_ref)) if len(valid_ref) > 0 else None
            curr_std = float(np.std(valid_curr)) if len(valid_curr) > 0 else None

            psi = calculate_psi(valid_ref, valid_curr)
            ks_stat, p_val = calculate_ks(valid_ref, valid_curr)

            if psi >= self.psi_sig_th:
                severity: ShiftSeverity = "significant"
                drift_detected = True
                significant_shifts.append(feat_name)
                interpretation = (
                    f"Significant distribution shift (PSI={psi:.4f} >= {self.psi_sig_th}, KS={ks_stat:.4f}). "
                    "Feature distribution differs markedly from baseline."
                )
            elif psi >= self.psi_mod_th:
                severity = "moderate"
                drift_detected = True
                moderate_shifts.append(feat_name)
                interpretation = (
                    f"Moderate distribution shift (PSI={psi:.4f} >= {self.psi_mod_th}, KS={ks_stat:.4f}). "
                    "Feature distribution exhibits mild divergence."
                )
            else:
                severity = "none"
                drift_detected = False
                interpretation = f"Distribution stable (PSI={psi:.4f} < {self.psi_mod_th}, KS={ks_stat:.4f})."

            feature_results[feat_name] = FeatureDriftResult(
                feature_name=feat_name,
                psi=round(psi, 4),
                ks_statistic=round(ks_stat, 4),
                p_value=round(p_val, 4),
                reference_count=len(valid_ref),
                current_count=len(valid_curr),
                reference_mean=round(ref_mean, 4) if ref_mean is not None else None,
                current_mean=round(curr_mean, 4) if curr_mean is not None else None,
                reference_std=round(ref_std, 4) if ref_std is not None else None,
                current_std=round(curr_std, 4) if curr_std is not None else None,
                missing_count_current=missing_curr,
                missing_rate_current=round(missing_rate, 4),
                shift_severity=severity,
                drift_detected=drift_detected,
                interpretation=interpretation,
            )

        overall_drift = len(significant_shifts) > 0 or len(moderate_shifts) > 0
        summary = (
            f"Evaluated {len(feature_results)} features on batch '{batch_id}' (n={batch_len}). "
            f"Overall drift: {'DETECTED' if overall_drift else 'NONE'}. "
            f"Significant shifts: {len(significant_shifts)}, Moderate shifts: {len(moderate_shifts)}."
        )

        return BatchDriftReport(
            batch_id=batch_id,
            reference_window=self.reference_window,
            sample_size=batch_len,
            features_monitored=list(feature_results.keys()),
            feature_results=feature_results,
            overall_drift_detected=overall_drift,
            significant_shift_features=significant_shifts,
            moderate_shift_features=moderate_shifts,
            summary=summary,
        )
