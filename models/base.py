"""Base model and probability calibration interfaces for SignalGate Gate G2.

Public interfaces:
- fit_base: Fits HistGradientBoostingClassifier or LogisticRegression on permitted training data.
- raw_score: Returns uncalibrated continuous probabilities from a fitted base model.
- fit_calibrator: Fits Platt (sigmoid) or Isotonic calibrator on the calibration partition.
- calibrated_p: Returns re-calibrated probabilities in [0, 1].
- brier_score, calibration_ece, reliability_curve_data: Diagnostic evaluation functions.

Architectural invariants:
- Base estimators must fit only on permitted training data; fitting on validation or test raises ValueError.
- Calibrators must fit only on permitted calibration data; fitting on validation or test raises ValueError.
- Output probabilities are strictly finite and bounded in [0.0, 1.0].
"""

from __future__ import annotations

from typing import Any, Literal
import numpy as np
from sklearn.calibration import calibration_curve
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss
from sklearn.pipeline import Pipeline as _Pipeline
from sklearn.preprocessing import StandardScaler

from models.calibration import IsotonicCalibrator, PlattCalibrator, calibration_ece

FORBIDDEN_FIT_PARTITIONS = {"validation", "test"}


def validate_fit_partition(partition: str, component_name: str, allowed: set[str]) -> None:
    """Ensure estimators and calibrators are never fitted on forbidden evaluation partitions."""
    norm = partition.strip().lower()
    if norm in FORBIDDEN_FIT_PARTITIONS or norm not in allowed:
        raise ValueError(
            f"Prohibited partition '{partition}' for fitting {component_name}. "
            f"Allowed partitions: {sorted(allowed)}. Fitting on validation or test data is strictly prohibited."
        )


def fit_base(
    model_type: Literal["hgbc", "lr"] | str,
    X_train: np.ndarray,
    y_train: np.ndarray,
    partition: str = "train",
    random_state: int = 11,
    **kwargs: Any,
) -> object:
    """Fit a base estimator strictly on the permitted training partition.

    Args:
        model_type: 'hgbc' (HistGradientBoostingClassifier) or 'lr' (LogisticRegression).
        X_train: Feature matrix, shape (n_samples, n_features).
        y_train: Binary labels, shape (n_samples,).
        partition: Partition name. Must be 'train' (or allowed training alias).
        random_state: Deterministic random seed.
        **kwargs: Optional model hyperparameters.

    Returns:
        Fitted scikit-learn estimator or pipeline.
    """
    validate_fit_partition(partition, f"base model '{model_type}'", {"train", "training"})

    X_train = np.asarray(X_train, dtype=np.float32)
    y_train = np.asarray(y_train, dtype=np.int32)

    model_type_norm = model_type.lower()
    if model_type_norm in ("hgbc", "histgradientboosting", "histgradientboostingclassifier"):
        max_iter = kwargs.pop("max_iter", 60)
        class_weight = kwargs.pop("class_weight", "balanced")
        clf = HistGradientBoostingClassifier(
            max_iter=max_iter,
            random_state=random_state,
            class_weight=class_weight,
            early_stopping=False,
            **kwargs,
        )
        clf.fit(X_train, y_train)
        return clf

    elif model_type_norm in ("lr", "logistic", "logisticregression"):
        max_iter = kwargs.pop("max_iter", 2000)
        C = kwargs.pop("C", 0.1)
        class_weight = kwargs.pop("class_weight", "balanced")
        pipeline = _Pipeline([
            ("imputer", SimpleImputer(strategy="median")),
            ("scaler", StandardScaler()),
            ("lr", LogisticRegression(
                solver="lbfgs",
                max_iter=max_iter,
                C=C,
                class_weight=class_weight,
                random_state=random_state,
                **kwargs,
            )),
        ])
        pipeline.fit(X_train, y_train)
        return pipeline

    else:
        raise ValueError(f"Unsupported model_type '{model_type}'. Expected 'hgbc' or 'lr'.")


def raw_score(estimator: object, X: np.ndarray) -> np.ndarray:
    """Return continuous uncalibrated probability scores in [0, 1].

    Args:
        estimator: Fitted base estimator or pipeline.
        X: Feature matrix, shape (n_samples, n_features).

    Returns:
        Probability vector of shape (n_samples,) representing P(Y=1|X).
    """
    X = np.asarray(X, dtype=np.float32)
    if not hasattr(estimator, "predict_proba"):
        raise AttributeError("Estimator does not implement predict_proba.")
    scores = estimator.predict_proba(X)[:, 1]  # type: ignore[union-attr]
    return np.asarray(scores, dtype=np.float64)


def fit_calibrator(
    method: Literal["sigmoid", "platt", "isotonic"] | str,
    cal_scores: np.ndarray,
    cal_labels: np.ndarray,
    partition: str = "calibration",
) -> object:
    """Fit a probability calibrator strictly on the calibration partition.

    Args:
        method: 'sigmoid' / 'platt' or 'isotonic'.
        cal_scores: Raw probability scores, shape (n_samples,).
        cal_labels: Ground truth binary labels, shape (n_samples,).
        partition: Partition name. Must be 'calibration' (or 'calib').

    Returns:
        Fitted PlattCalibrator or IsotonicCalibrator.
    """
    validate_fit_partition(partition, f"calibrator '{method}'", {"calibration", "calib"})

    method_norm = method.lower()
    if method_norm in ("sigmoid", "platt"):
        calibrator = PlattCalibrator()
        calibrator.fit(cal_scores, cal_labels)
        return calibrator
    elif method_norm == "isotonic":
        calibrator = IsotonicCalibrator()
        calibrator.fit(cal_scores, cal_labels)
        return calibrator
    else:
        raise ValueError(f"Unsupported calibration method '{method}'. Expected 'sigmoid'/'platt' or 'isotonic'.")


def calibrated_p(calibrator: object, scores: np.ndarray) -> np.ndarray:
    """Return calibrated probabilities in [0, 1] using a fitted calibrator.

    Args:
        calibrator: Fitted PlattCalibrator or IsotonicCalibrator.
        scores: Raw probability scores, shape (n_samples,).

    Returns:
        Calibrated probabilities in [0, 1], shape (n_samples,).
    """
    if not hasattr(calibrator, "predict_proba"):
        raise AttributeError("Calibrator does not implement predict_proba.")
    probs = calibrator.predict_proba(scores)  # type: ignore[union-attr]
    probs = np.asarray(probs, dtype=np.float64)
    if not np.all(np.isfinite(probs)):
        raise ValueError("Calibrated probabilities contain non-finite values (NaN or Inf).")
    return np.clip(probs, 0.0, 1.0)


def brier_score(y_true: np.ndarray, scores: np.ndarray) -> float:
    """Calculate mean squared error between binary labels and predicted probabilities."""
    y_true = np.asarray(y_true, dtype=np.int32)
    scores = np.asarray(scores, dtype=np.float64)
    if len(y_true) == 0:
        return 0.0
    return float(brier_score_loss(y_true, scores))


def reliability_curve_data(
    scores: np.ndarray,
    labels: np.ndarray,
    n_bins: int = 10,
    strategy: str = "uniform",
) -> tuple[np.ndarray, np.ndarray]:
    """Compute empirical fraud fraction and mean predicted probability per bin.

    Returns:
        (prob_true, prob_pred) arrays.
    """
    scores = np.asarray(scores, dtype=np.float64)
    labels = np.asarray(labels, dtype=np.int32)
    if len(scores) == 0:
        return np.array([]), np.array([])
    prob_true, prob_pred = calibration_curve(labels, scores, n_bins=n_bins, strategy=strategy)
    return prob_true, prob_pred
