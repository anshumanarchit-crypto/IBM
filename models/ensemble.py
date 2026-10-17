"""Era-bagged heterogeneous ensemble for SignalGate Gate G2.

Architecture:
- 5 x HistGradientBoostingClassifier (seeds 11, 22, 33, 44, 55)
- 1 x ExtraTreesClassifier (seed 11)
- 1 x LogisticRegression (seed 11, on preprocessed features)

All base estimators are trained strictly on the training partition with the
feature matrix produced by FeaturePipeline. No data from calibration, validation,
or test is used during fitting.

The ensemble probability p_ens is the simple arithmetic mean of individual
predicted probabilities. The per-member scores vector is retained and passed to
models/signals for disagreement signal extraction.

Chronological Era Bagging:
- Training partition is divided into 5 chronological eras.
- EraBaggedHeterogeneousEnsemble trains members that each omit one chronological era.
- Era assignment uses training rows only; calibration, validation, and test are strictly excluded.

Constraints:
- `isFraud`, `TransactionID`, `TransactionDT` never enter the feature matrix.
- Each base estimator uses a deterministic random_state from config.yaml seeds.
- Only validation data is used for tuning; test data is never inspected.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import numpy as np
from sklearn.ensemble import (
    ExtraTreesClassifier,
    HistGradientBoostingClassifier,
)
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline as _Pipeline
from sklearn.preprocessing import StandardScaler


# G2 reproducibility seeds (from config.yaml)
SEEDS: tuple[int, ...] = (11, 22, 33, 44, 55)


def compute_training_eras(n_samples: int, n_eras: int = 5) -> list[tuple[int, int]]:
    """Divide training observations chronologically into approximately equal eras.

    Args:
        n_samples: Total number of training rows.
        n_eras: Number of chronological eras (default 5).

    Returns:
        List of (start_index, end_index) half-open intervals spanning [0, n_samples).
    """
    if n_samples <= 0:
        raise ValueError("n_samples must be positive.")
    if n_eras <= 0 or n_eras > n_samples:
        raise ValueError(f"Invalid n_eras {n_eras} for n_samples {n_samples}.")

    step = n_samples / n_eras
    eras: list[tuple[int, int]] = []
    for i in range(n_eras):
        start = int(round(i * step))
        end = int(round((i + 1) * step)) if i < n_eras - 1 else n_samples
        eras.append((start, end))
    return eras


def get_era_omitted_indices(n_samples: int, omit_era_idx: int, n_eras: int = 5) -> np.ndarray:
    """Return indices of training data omitting one chronological era."""
    eras = compute_training_eras(n_samples, n_eras=n_eras)
    if not (0 <= omit_era_idx < n_eras):
        raise IndexError(f"omit_era_idx {omit_era_idx} out of range for {n_eras} eras.")
    start, end = eras[omit_era_idx]
    mask = np.ones(n_samples, dtype=bool)
    mask[start:end] = False
    return np.flatnonzero(mask)


@dataclass
class MemberPredictions:
    """Per-member raw probabilities returned by the ensemble.

    Shape of `proba_matrix`: (n_samples, n_members).
    Shape of `member_ids`:   (n_members,) — human-readable model labels.
    """

    proba_matrix: np.ndarray  # shape (n, n_members)
    member_ids: list[str]


class HeterogeneousEnsemble:
    """Heterogeneous ensemble fitted on the training partition.

    Members:
      - hgbc_s{seed}: HistGradientBoostingClassifier per seed in SEEDS (11, 22, 33, 44, 55)
      - et_s11:       ExtraTreesClassifier, seed 11
      - lr_s11:       LogisticRegression with SimpleImputer + StandardScaler, seed 11
    """

    def __init__(self, seeds: Sequence[int] = SEEDS) -> None:
        self.seeds = list(seeds)
        self._members: list[tuple[str, object]] = []
        self.member_ids: list[str] = []
        self.is_fitted = False

    def _build_members(self) -> list[tuple[str, object]]:
        members: list[tuple[str, object]] = []

        # 5 x HistGradientBoostingClassifier
        for seed in self.seeds:
            members.append((
                f"hgbc_s{seed}",
                HistGradientBoostingClassifier(
                    max_iter=60,
                    random_state=seed,
                    class_weight="balanced",
                    early_stopping=False,
                ),
            ))

        # 1 x ExtraTreesClassifier
        members.append((
            "et_s11",
            ExtraTreesClassifier(
                n_estimators=200,
                random_state=11,
                class_weight="balanced",
                n_jobs=-1,
            ),
        ))

        # 1 x LogisticRegression wrapped with imputation + scaling.
        members.append((
            "lr_s11",
            _Pipeline([
                ("imputer", SimpleImputer(strategy="median")),
                ("scaler", StandardScaler()),
                ("lr", LogisticRegression(
                    solver="lbfgs",
                    max_iter=2000,
                    C=0.1,
                    class_weight="balanced",
                    random_state=11,
                )),
            ]),
        ))

        return members

    def fit(self, X_train: np.ndarray, y_train: np.ndarray) -> "HeterogeneousEnsemble":
        """Fit all members on the training partition."""
        self._members = self._build_members()
        for name, estimator in self._members:
            estimator.fit(X_train, y_train)  # type: ignore[union-attr]
        self.member_ids = [name for name, _ in self._members]
        self.is_fitted = True
        return self

    def predict_member_proba(self, X: np.ndarray) -> MemberPredictions:
        """Return per-member probabilities without averaging."""
        if not self.is_fitted:
            raise RuntimeError("HeterogeneousEnsemble must be fitted first")

        X = np.asarray(X, dtype=np.float32)
        cols = []
        for _, estimator in self._members:
            p = estimator.predict_proba(X)[:, 1]  # type: ignore[union-attr]
            cols.append(p.astype(np.float64))

        proba_matrix = np.column_stack(cols)  # shape (n, n_members)
        return MemberPredictions(proba_matrix=proba_matrix, member_ids=list(self.member_ids))

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        """Return ensemble mean probability, shape (n,)."""
        mp = self.predict_member_proba(X)
        return mp.proba_matrix.mean(axis=1)

    @property
    def n_members(self) -> int:
        return len(self._members)

    def get_member(self, name: str) -> object:
        """Retrieve a specific member estimator by its identifier."""
        for member_name, estimator in self._members:
            if member_name == name:
                return estimator
        raise KeyError(f"Member '{name}' not found in ensemble members: {self.member_ids}")


class EraBaggedHeterogeneousEnsemble:
    """Ensemble where each member is trained omitting one chronological era of training data.

    Rotates model types across members (HistGradientBoosting, ExtraTrees, LogisticRegression)
    using deterministic seeds.
    """

    def __init__(self, n_eras: int = 5) -> None:
        self.n_eras = n_eras
        self._members: list[tuple[str, object, tuple[int, int]]] = []
        self.member_ids: list[str] = []
        self.era_definitions: list[tuple[int, int]] = []
        self.is_fitted = False

    def _build_member_specs(self) -> list[tuple[str, object]]:
        specs = [
            ("era0_omit_hgbc_s11", HistGradientBoostingClassifier(max_iter=60, random_state=11, class_weight="balanced", early_stopping=False)),
            ("era1_omit_hgbc_s22", HistGradientBoostingClassifier(max_iter=60, random_state=22, class_weight="balanced", early_stopping=False)),
            ("era2_omit_et_s11", ExtraTreesClassifier(n_estimators=100, random_state=11, class_weight="balanced", n_jobs=-1)),
            ("era3_omit_lr_s11", _Pipeline([
                ("imputer", SimpleImputer(strategy="median")),
                ("scaler", StandardScaler()),
                ("lr", LogisticRegression(solver="lbfgs", max_iter=2000, C=0.1, class_weight="balanced", random_state=11)),
            ])),
            ("era4_omit_hgbc_s33", HistGradientBoostingClassifier(max_iter=60, random_state=33, class_weight="balanced", early_stopping=False)),
        ]
        return specs[:self.n_eras]

    def fit(self, X_train: np.ndarray, y_train: np.ndarray) -> "EraBaggedHeterogeneousEnsemble":
        """Fit era-bagged members omitting one training era per member."""
        n_samples = len(X_train)
        self.era_definitions = compute_training_eras(n_samples, n_eras=self.n_eras)
        specs = self._build_member_specs()

        self._members = []
        for era_idx, (name, estimator) in enumerate(specs):
            train_idx = get_era_omitted_indices(n_samples, omit_era_idx=era_idx, n_eras=self.n_eras)
            estimator.fit(X_train[train_idx], y_train[train_idx])  # type: ignore[union-attr]
            self._members.append((name, estimator, self.era_definitions[era_idx]))

        self.member_ids = [m[0] for m in self._members]
        self.is_fitted = True
        return self

    def predict_member_proba(self, X: np.ndarray) -> MemberPredictions:
        if not self.is_fitted:
            raise RuntimeError("EraBaggedHeterogeneousEnsemble must be fitted first")

        X = np.asarray(X, dtype=np.float32)
        cols = []
        for _, estimator, _ in self._members:
            p = estimator.predict_proba(X)[:, 1]  # type: ignore[union-attr]
            cols.append(p.astype(np.float64))

        proba_matrix = np.column_stack(cols)
        return MemberPredictions(proba_matrix=proba_matrix, member_ids=list(self.member_ids))

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        mp = self.predict_member_proba(X)
        return mp.proba_matrix.mean(axis=1)

    @property
    def n_members(self) -> int:
        return len(self._members)
