"""SignalGate Candidate Policy (P5) Implementation for Gate G2.

Audit Note:
Prior to Gate G2 closure, no concrete mathematical formula for P5 was implemented
in source code or committed configuration.

This module defines the transparent, deterministic Candidate P5 Policy:
  score(x) = p_calibrated(x) + lambda * u_signal(x)

Where:
  p_calibrated: Platt-calibrated probability from the era-bagged heterogeneous ensemble.
  u_signal:     Disagreement signal (u = ensemble std, or u2 = ensemble MAD).
  lambda:       Triage disagreement weight in [0.0, 1.0].

Empirical Weight Selection on Validation Partition:
  Validation ablation demonstrated that adding disagreement (lambda > 0) produces no
  statistically significant recall gain over pure ensemble risk ranking:
    Delta Recall (Risk + u vs Ensemble Risk): mean = -0.087%, 95% CI = [-0.403%, +0.237%].
  Consequently, the default pre-registered weight is lambda = 0.0 (retaining the
  ensemble risk ranking which provides a verified +1.096% to +1.330% recall gain over B2),
  with u and u2 preserved as explanatory/audit governance signals for LLM agents.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Literal

import numpy as np


@dataclass(frozen=True)
class P5PolicyConfig:
    """Configuration contract for Candidate P5 Policy."""

    name: str = "P5_SignalGate_Candidate"
    version: str = "0.2.0"
    base_ensemble: str = "EraBaggedHeterogeneousEnsemble"
    calibration_method: str = "platt_sigmoid"
    disagreement_signal: Literal["none", "u", "u2"] = "u2"
    disagreement_weight_lambda: float = 0.0
    budget_multiple: float = 1.5

    def config_hash(self) -> str:
        """Deterministic SHA-256 hash of configuration payload."""
        payload = {
            "name": self.name,
            "version": self.version,
            "base_ensemble": self.base_ensemble,
            "calibration_method": self.calibration_method,
            "disagreement_signal": self.disagreement_signal,
            "disagreement_weight_lambda": self.disagreement_weight_lambda,
            "budget_multiple": self.budget_multiple,
        }
        raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(raw).hexdigest()


class CandidateP5Policy:
    """Candidate P5 Decision Support Triage Router."""

    def __init__(self, config: P5PolicyConfig | None = None) -> None:
        self.config = config or P5PolicyConfig()

    def score(
        self,
        p_calibrated: np.ndarray,
        disagreement: np.ndarray | None = None,
    ) -> np.ndarray:
        """Calculate combined triage priority score."""
        p = np.asarray(p_calibrated, dtype=np.float64)
        if self.config.disagreement_weight_lambda == 0.0 or disagreement is None:
            return p

        u = np.asarray(disagreement, dtype=np.float64)
        return p + self.config.disagreement_weight_lambda * u

    def route(
        self,
        scores: np.ndarray,
        transaction_ids: np.ndarray,
        train_prevalence: float,
        total_cases: int | None = None,
    ) -> np.ndarray:
        """Assign review decisions based on top-budget ranking with deterministic tie handling.

        Returns binary array (1 = ESCALATE_TO_REVIEW, 0 = AUTO_CLEAR).
        """
        scores = np.asarray(scores, dtype=np.float64)
        tx_ids = np.asarray(transaction_ids)
        n = total_cases if total_cases is not None else len(scores)

        # Budget calculation: Multiple * train_prevalence * total_cases
        k = int(np.floor(self.config.budget_multiple * train_prevalence * n))
        k = max(0, min(k, len(scores)))

        if k == 0:
            return np.zeros(len(scores), dtype=np.int32)
        if k >= len(scores):
            return np.ones(len(scores), dtype=np.int32)

        # Deterministic sorting: primary = -score, secondary = TransactionID ascending
        order = np.lexsort((tx_ids, -scores))
        selected_indices = order[:k]

        decisions = np.zeros(len(scores), dtype=np.int32)
        decisions[selected_indices] = 1
        return decisions
