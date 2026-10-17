"""Tests for chronological splits and temporal partition isolation."""

import numpy as np
import pandas as pd
import pytest

from data.splits import ChronologicalSplitter, compute_partition_hash


@pytest.fixture
def synthetic_transactions() -> pd.DataFrame:
    """Create a synthetic transaction dataframe with known chronological ordering."""
    n = 1000
    return pd.DataFrame({
        "TransactionID": np.arange(1000, 1000 + n),
        "TransactionDT": np.arange(10000, 10000 + n * 10, 10),
        "TransactionAmt": np.random.uniform(5.0, 500.0, n),
        "isFraud": np.random.binomial(1, 0.05, n),
    })


def test_chronological_splits_proportions_and_disjointness(synthetic_transactions: pd.DataFrame):
    splitter = ChronologicalSplitter()
    partitions = splitter.split(synthetic_transactions, sort=True)

    assert set(partitions.keys()) == {"train", "calibration", "validation", "test"}

    # Proportions: 60%, 10%, 10%, 20%
    n = len(synthetic_transactions)
    assert len(partitions["train"]) == int(round(n * 0.60))
    assert len(partitions["calibration"]) == int(round(n * 0.10))
    assert len(partitions["validation"]) == int(round(n * 0.10))
    assert len(partitions["test"]) == int(round(n * 0.20))
    assert sum(len(p) for p in partitions.values()) == n

    # Disjointness of TransactionIDs
    all_ids = []
    for p_df in partitions.values():
        all_ids.extend(p_df["TransactionID"].tolist())
    assert len(all_ids) == len(set(all_ids)), "Partitions contain duplicate TransactionIDs!"


def test_strict_temporal_ordering_no_leakage(synthetic_transactions: pd.DataFrame):
    splitter = ChronologicalSplitter()
    partitions = splitter.split(synthetic_transactions, sort=True)

    train_max_dt = partitions["train"]["TransactionDT"].max()
    cal_min_dt = partitions["calibration"]["TransactionDT"].min()
    cal_max_dt = partitions["calibration"]["TransactionDT"].max()
    val_min_dt = partitions["validation"]["TransactionDT"].min()
    val_max_dt = partitions["validation"]["TransactionDT"].max()
    test_min_dt = partitions["test"]["TransactionDT"].min()

    assert cal_min_dt > train_max_dt, "Temporal leakage: calibration overlaps with train!"
    assert val_min_dt > cal_max_dt, "Temporal leakage: validation overlaps with calibration!"
    assert test_min_dt > val_max_dt, "Temporal leakage: test overlaps with validation!"


def test_partition_hash_reproducibility():
    ids = np.array([101, 102, 103, 104])
    hash1 = compute_partition_hash(ids)
    hash2 = compute_partition_hash(ids)
    assert hash1 == hash2
    assert len(hash1) == 64

    # Order sensitive
    hash_rev = compute_partition_hash(np.array([104, 103, 102, 101]))
    assert hash1 != hash_rev


def test_splitter_metadata_calculation(synthetic_transactions: pd.DataFrame):
    splitter = ChronologicalSplitter()
    partitions = splitter.split(synthetic_transactions)
    meta = splitter.get_metadata(partitions)

    for name in ["train", "calibration", "validation", "test"]:
        assert name in meta
        m = meta[name]
        assert m.row_count == len(partitions[name])
        assert m.fraud_count + m.non_fraud_count == m.row_count
        assert 0.0 <= m.prevalence <= 1.0
        assert len(m.split_hash) == 64
