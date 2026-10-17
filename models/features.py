"""Feature manifest and learned preprocessing pipeline for SignalGate.

Strictly excludes target labels (isFraud) and raw identifiers/timestamps
(TransactionID, TransactionDT). Fits learned encoders solely on the training partition.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.preprocessing import OrdinalEncoder

FORBIDDEN_INPUT_COLUMNS = {
    "isFraud",
    "TransactionID",
    "TransactionDT",
}


@dataclass(frozen=True)
class FeatureManifest:
    """Documented feature manifest and transformation definitions."""

    target_column: str
    excluded_columns: list[str]
    categorical_columns: list[str]
    numerical_columns: list[str]
    feature_count: int
    feature_names: list[str]


class FeaturePipeline:
    """Learned preprocessing pipeline fitted solely on the training partition."""

    def __init__(self, max_features: int | None = None):
        self.max_features = max_features
        self.encoder: OrdinalEncoder | None = None
        self.categorical_cols: list[str] = []
        self.numerical_cols: list[str] = []
        self.feature_names: list[str] = []
        self.is_fitted = False

    def fit(self, train_df: pd.DataFrame) -> "FeaturePipeline":
        """Learn categoricals and feature columns strictly from the training partition."""
        candidates = [col for col in train_df.columns if col not in FORBIDDEN_INPUT_COLUMNS]

        # Categoricals (non-numeric columns)
        self.categorical_cols = [
            col for col in candidates if not pd.api.types.is_numeric_dtype(train_df[col])
        ]

        # Numerical columns
        self.numerical_cols = [
            col for col in candidates if pd.api.types.is_numeric_dtype(train_df[col])
        ]

        # Fit ordinal encoder on categoricals
        if self.categorical_cols:
            self.encoder = OrdinalEncoder(
                handle_unknown="use_encoded_value",
                unknown_value=-1,
                encoded_missing_value=-1,
            )
            cat_data = train_df[self.categorical_cols].astype(str)
            self.encoder.fit(cat_data)

        self.feature_names = self.numerical_cols + self.categorical_cols
        self.is_fitted = True
        return self

    def transform(self, df: pd.DataFrame) -> np.ndarray:
        """Transform dataframe into feature matrix X using fitted pipeline."""
        if not self.is_fitted:
            raise RuntimeError("FeaturePipeline must be fitted before transform")

        # Verify no forbidden columns are used in features
        num_part = df[self.numerical_cols].values.astype(np.float32)

        if self.categorical_cols and self.encoder is not None:
            cat_data = df[self.categorical_cols].astype(str)
            cat_part = self.encoder.transform(cat_data).astype(np.float32)
            X = np.hstack([num_part, cat_part])
        else:
            X = num_part

        return X

    def fit_transform(self, train_df: pd.DataFrame) -> np.ndarray:
        return self.fit(train_df).transform(train_df)

    def get_manifest(self) -> FeatureManifest:
        if not self.is_fitted:
            raise RuntimeError("Pipeline must be fitted to generate manifest")
        return FeatureManifest(
            target_column="isFraud",
            excluded_columns=sorted(list(FORBIDDEN_INPUT_COLUMNS)),
            categorical_columns=self.categorical_cols,
            numerical_columns=self.numerical_cols,
            feature_count=len(self.feature_names),
            feature_names=self.feature_names,
        )

    def save_manifest(self, out_path: str | Path) -> None:
        manifest = self.get_manifest()
        p = Path(out_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(asdict(manifest), indent=2), encoding="utf-8")
