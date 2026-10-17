"""Disagreement signal extraction and interface contracts for SignalGate Gate G2.

Computes two scalar disagreement signals from the per-member probability matrix
produced by HeterogeneousEnsemble:

  u  -- standard deviation across ensemble members (aleatoric/epistemic spread).
  u2 -- mean absolute deviation from the median (robust spread, less outlier-sensitive).

Both signals are non-negative scalars attached to an AuditRecord.  They are
exposed to agents only through the AgentCaseView allowlist (p, u, u2, n) and
are never computed from or compared against ground-truth labels during inference.

Signal definitions (for n members, scores vector s_1 ... s_m):
  u  = std(s_1, ..., s_m)  [population std-dev, ddof=0]
  u2 = mean(|s_i - median(s)|)
  n  = number of members (informational)

Signal lifecycle & partition governance:
  - Base estimators and signals may fit only on permitted development/training/calibration partitions.
  - Fitting on 'validation' or 'test' raises a ValueError.
  - Every signal component tracks its status: 'ok', 'skipped', or 'failed'.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Literal

import numpy as np
from scipy import stats

from models.ensemble import MemberPredictions

SignalStatus = Literal["unfitted", "ok", "skipped", "failed"]
FORBIDDEN_SIGNAL_PARTITIONS = {"validation", "test"}


def validate_signal_fit_partition(partition: str, signal_name: str) -> None:
    """Prohibit signal or calibrator fitting on validation or test partitions."""
    norm = partition.strip().lower()
    if norm in FORBIDDEN_SIGNAL_PARTITIONS:
        raise ValueError(
            f"Prohibited partition '{partition}' for fitting signal '{signal_name}'. "
            f"Fitting on validation or test partitions is strictly forbidden."
        )


class BaseSignal(ABC):
    """Abstract base class for SignalGate candidate signals."""

    def __init__(self, name: str) -> None:
        self.name = name
        self.status: SignalStatus = "unfitted"
        self._error_message: str | None = None

    @abstractmethod
    def _fit_internal(self, X: np.ndarray, y: np.ndarray | None = None) -> None:
        """Internal fitting logic implemented by concrete signals."""
        raise NotImplementedError

    def fit(self, partition: str, X: np.ndarray, y: np.ndarray | None = None) -> BaseSignal:
        """Fit signal extractor on permitted development partition with partition enforcement."""
        validate_signal_fit_partition(partition, self.name)
        try:
            self._fit_internal(X, y)
            self.status = "ok"
        except Exception as exc:
            self.status = "failed"
            self._error_message = str(exc)
            raise
        return self

    def skip(self, reason: str = "Permitted skip") -> None:
        """Explicitly record a permitted skip (distinct from failure)."""
        self.status = "skipped"
        self._error_message = reason

    @abstractmethod
    def score(self, X: np.ndarray) -> np.ndarray:
        """Generate signal scores for input matrix."""
        raise NotImplementedError


class DisagreementSignalExtractor(BaseSignal):
    """Extracts ensemble standard deviation u across members."""

    def __init__(self, name: str = "disagreement_std_u") -> None:
        super().__init__(name=name)

    def _fit_internal(self, X: np.ndarray, y: np.ndarray | None = None) -> None:
        # Transformation requires no parameters learned from labels
        pass

    def score(self, member_proba_matrix: np.ndarray) -> np.ndarray:
        P = np.asarray(member_proba_matrix, dtype=np.float64)
        if P.ndim != 2:
            raise ValueError(f"Expected 2D probability matrix, got shape {P.shape}")
        return P.std(axis=1, ddof=0)


class RobustDisagreementSignalExtractor(BaseSignal):
    """Extracts median absolute deviation u2 from ensemble median."""

    def __init__(self, name: str = "robust_disagreement_mad_u2") -> None:
        super().__init__(name=name)

    def _fit_internal(self, X: np.ndarray, y: np.ndarray | None = None) -> None:
        pass

    def score(self, member_proba_matrix: np.ndarray) -> np.ndarray:
        P = np.asarray(member_proba_matrix, dtype=np.float64)
        if P.ndim != 2:
            raise ValueError(f"Expected 2D probability matrix, got shape {P.shape}")
        med = np.median(P, axis=1)
        return np.mean(np.abs(P - med[:, None]), axis=1)


@dataclass(frozen=True)
class DisagreementSignals:
    """Scalar disagreement signals derived from one sample's member scores.

    Attributes:
        u:  Ensemble standard deviation across members.
        u2: Mean absolute deviation from the ensemble median.
        n:  Number of ensemble members (informational).
        p:  Ensemble mean probability (convenience copy).
    """

    p: float
    u: float
    u2: float
    n: float


def compute_signals(mp: MemberPredictions) -> np.ndarray:
    """Compute (p, u, u2, n) vectors from a MemberPredictions object.

    Args:
        mp: MemberPredictions with proba_matrix shape (n_samples, n_members).

    Returns:
        Structured numpy array with fields p, u, u2, n; shape (n_samples,).
        Each row corresponds to one transaction.
    """
    P = mp.proba_matrix  # shape (n_samples, n_members)
    n_samples, n_members = P.shape

    p_mean = P.mean(axis=1)                                   # ensemble mean
    u_std = P.std(axis=1, ddof=0)                             # population std-dev
    p_median = np.median(P, axis=1)                           # median per row
    u2_mad = np.mean(np.abs(P - p_median[:, None]), axis=1)  # MAD from median
    n_vec = np.full(n_samples, float(n_members))

    dtype = np.dtype([
        ("p", np.float64),
        ("u", np.float64),
        ("u2", np.float64),
        ("n", np.float64),
    ])
    out = np.empty(n_samples, dtype=dtype)
    out["p"] = p_mean
    out["u"] = u_std
    out["u2"] = u2_mad
    out["n"] = n_vec
    return out


def compute_signals_for_sample(member_scores: np.ndarray) -> DisagreementSignals:
    """Compute signals for a single sample's per-member scores.

    Args:
        member_scores: 1-D array of shape (n_members,).

    Returns:
        DisagreementSignals with p, u, u2, n.
    """
    s = np.asarray(member_scores, dtype=np.float64)
    p = float(s.mean())
    u = float(s.std(ddof=0))
    u2 = float(np.mean(np.abs(s - np.median(s))))
    n = float(len(s))
    return DisagreementSignals(p=p, u=u, u2=u2, n=n)


def spearman_rank_correlation(x: np.ndarray, y: np.ndarray) -> float:
    """Compute Spearman rank-order correlation between two scalar series.

    Returns:
        Correlation coefficient in [-1.0, 1.0].
    """
    x = np.asarray(x, dtype=np.float64)
    y = np.asarray(y, dtype=np.float64)
    if len(x) == 0 or len(y) == 0:
        return 0.0
    res = stats.spearmanr(x, y)
    corr = res.statistic if hasattr(res, "statistic") else res[0]
    return float(corr) if np.isfinite(corr) else 0.0


def paired_bootstrap_recall_difference(
    y_true: np.ndarray,
    scores_baseline: np.ndarray,
    scores_candidate: np.ndarray,
    budget_count: int,
    n_resamples: int = 1000,
    random_state: int = 11,
    confidence_level: float = 0.95,
) -> dict[str, float | bool]:
    """Calculate paired-bootstrap confidence interval for recall difference (Candidate - Baseline).

    Both policies are evaluated on the exact same resampled rows at an identical review workload.

    Returns:
        Dictionary with:
          delta_mean: mean recall difference
          ci_lower: lower bound of confidence interval
          ci_upper: upper bound of confidence interval
          significant_positive: True if ci_lower > 0
    """
    y_true = np.asarray(y_true, dtype=np.int32)
    s_base = np.asarray(scores_baseline, dtype=np.float64)
    s_cand = np.asarray(scores_candidate, dtype=np.float64)
    n = len(y_true)
    if n == 0 or budget_count <= 0:
        return {
            "delta_mean": 0.0,
            "ci_lower": 0.0,
            "ci_upper": 0.0,
            "significant_positive": False,
        }

    rng = np.random.default_rng(random_state)
    deltas = np.empty(n_resamples, dtype=np.float64)

    for i in range(n_resamples):
        idx = rng.choice(n, size=n, replace=True)
        y_b = y_true[idx]
        total_pos = np.sum(y_b == 1)
        if total_pos == 0:
            deltas[i] = 0.0
            continue

        s_b_base = s_base[idx]
        s_b_cand = s_cand[idx]

        # Top-budget selection on resampled observations
        k = min(budget_count, n)
        # Baseline top-k
        base_top_idx = np.argpartition(-s_b_base, k - 1)[:k]
        recall_base = np.sum(y_b[base_top_idx] == 1) / total_pos

        # Candidate top-k
        cand_top_idx = np.argpartition(-s_b_cand, k - 1)[:k]
        recall_cand = np.sum(y_b[cand_top_idx] == 1) / total_pos

        deltas[i] = float(recall_cand - recall_base)

    alpha = (1.0 - confidence_level) / 2.0
    ci_lower = float(np.percentile(deltas, 100.0 * alpha))
    ci_upper = float(np.percentile(deltas, 100.0 * (1.0 - alpha)))
    delta_mean = float(np.mean(deltas))

    return {
        "delta_mean": delta_mean,
        "ci_lower": ci_lower,
        "ci_upper": ci_upper,
        "significant_positive": bool(ci_lower > 0.0),
    }
