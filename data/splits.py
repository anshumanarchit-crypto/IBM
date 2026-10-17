"""Chronological, leakage-safe data partitioning for SignalGate.

Enforces strict temporal ordering:
- Train: First 60%
- Calibration: Next 10%
- Validation: Next 10%
- Test: Final 20%
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal

import numpy as np
import pandas as pd

PartitionName = Literal["train", "calibration", "validation", "test"]

DEFAULT_SPLIT_RATIOS = {
    "train": (0.0, 0.60),
    "calibration": (0.60, 0.70),
    "validation": (0.70, 0.80),
    "test": (0.80, 1.00),
}


@dataclass(frozen=True)
class PartitionMetadata:
    """Audit metadata for one chronological partition."""

    name: str
    start_idx: int
    end_idx: int
    row_count: int
    dt_min: int
    dt_max: int
    fraud_count: int
    non_fraud_count: int
    prevalence: float
    split_hash: str


def compute_partition_hash(ids: pd.Series | np.ndarray) -> str:
    """Compute a deterministic SHA-256 fingerprint for a sequence of TransactionIDs."""
    id_bytes = ",".join(str(int(x)) for x in ids).encode("ascii")
    return hashlib.sha256(id_bytes).hexdigest()


class ChronologicalSplitter:
    """Partitions transactions chronologically by TransactionDT with zero lookahead."""

    def __init__(self, ratios: dict[str, tuple[float, float]] | None = None):
        self.ratios = ratios or DEFAULT_SPLIT_RATIOS

    def split(
        self,
        df: pd.DataFrame,
        sort: bool = True,
    ) -> dict[PartitionName, pd.DataFrame]:
        """Split dataframe into 4 chronological partitions."""
        if "TransactionDT" not in df.columns:
            raise ValueError("DataFrame must contain 'TransactionDT'")
        if "TransactionID" not in df.columns:
            raise ValueError("DataFrame must contain 'TransactionID'")

        working_df = df.sort_values("TransactionDT", kind="mergesort").reset_index(drop=True) if sort else df

        n = len(working_df)
        partitions: dict[PartitionName, pd.DataFrame] = {}

        for name, (start_ratio, end_ratio) in self.ratios.items():
            start_idx = int(round(n * start_ratio))
            end_idx = int(round(n * end_ratio))
            partition_df = working_df.iloc[start_idx:end_idx].copy().reset_index(drop=True)
            partitions[name] = partition_df

        return partitions

    def get_metadata(
        self,
        partitions: dict[PartitionName, pd.DataFrame],
    ) -> dict[str, PartitionMetadata]:
        """Calculate audit metadata and cryptographic split hashes for each partition."""
        meta: dict[str, PartitionMetadata] = {}
        for name, p_df in partitions.items():
            row_count = len(p_df)
            dt_min = int(p_df["TransactionDT"].min()) if row_count > 0 else 0
            dt_max = int(p_df["TransactionDT"].max()) if row_count > 0 else 0

            if "isFraud" in p_df.columns:
                fraud_count = int((p_df["isFraud"] == 1).sum())
                non_fraud_count = int((p_df["isFraud"] == 0).sum())
                prevalence = float(fraud_count / row_count) if row_count > 0 else 0.0
            else:
                fraud_count = -1
                non_fraud_count = -1
                prevalence = -1.0

            split_hash = compute_partition_hash(p_df["TransactionID"].values)

            start_ratio, end_ratio = self.ratios[name]
            meta[name] = PartitionMetadata(
                name=name,
                start_idx=int(round(len(p_df) * start_ratio)),
                end_idx=int(round(len(p_df) * end_ratio)),
                row_count=row_count,
                dt_min=dt_min,
                dt_max=dt_max,
                fraud_count=fraud_count,
                non_fraud_count=non_fraud_count,
                prevalence=prevalence,
                split_hash=split_hash,
            )
        return meta


def load_and_split(
    raw_path: str | Path,
    manifest_out: str | Path | None = None,
) -> tuple[dict[PartitionName, pd.DataFrame], dict[str, PartitionMetadata]]:
    """Load labeled train_transaction.csv, execute chronological split, and save manifest."""
    raw_path = Path(raw_path)
    tx_file = raw_path / "train_transaction.csv" if raw_path.is_dir() else raw_path

    if not tx_file.exists():
        raise FileNotFoundError(f"Missing train transaction file: {tx_file}")

    df = pd.read_csv(tx_file)
    splitter = ChronologicalSplitter()
    partitions = splitter.split(df, sort=True)
    metadata = splitter.get_metadata(partitions)

    if manifest_out:
        out_path = Path(manifest_out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_data = {
            "total_rows": len(df),
            "partitions": {k: asdict(v) for k, v in metadata.items()},
        }
        out_path.write_text(json.dumps(manifest_data, indent=2), encoding="utf-8")

    return partitions, metadata
