"""Tests for Shift Scenarios (S0, S1, S2, S3) and data governance (Gate G4)."""

import json
from pathlib import Path
import numpy as np
import pandas as pd
import pytest

from data.shift_scenarios import (
    SCENARIO_SPECS,
    build_scenario_s2,
    build_scenario_s3,
    export_scenario_manifest,
    get_scenario_specs,
)


def test_scenario_specs_completeness_and_governance():
    """Verify that all four required shift scenarios are registered and well-formed."""
    specs = get_scenario_specs()
    assert set(specs.keys()) == {"S0", "S1", "S2", "S3"}

    # S0: Original chronological test set
    s0 = specs["S0"]
    assert s0.scenario_id == "S0"
    assert s0.source_partition == "test"
    assert s0.is_synthetic is False
    assert s0.dt_min == 12192900
    assert s0.dt_max == 15811131
    assert s0.expected_row_count == 118108
    assert "Historical baseline metrics" in s0.governance_notes

    # S1: Late-period chronological test scenario
    s1 = specs["S1"]
    assert s1.scenario_id == "S1"
    assert s1.source_partition == "test"
    assert s1.is_synthetic is False
    assert s1.dt_min == 14800000

    # S2: Constructed real-data shift
    s2 = specs["S2"]
    assert s2.scenario_id == "S2"
    assert s2.source_partition == "validation"
    assert s2.is_synthetic is False
    assert s2.dt_min == 11315422
    assert "Zero exposure to the test partition" in s2.governance_notes

    # S3: Synthetic perturbation scenario
    s3 = specs["S3"]
    assert s3.scenario_id == "S3"
    assert s3.source_partition == "validation"
    assert s3.is_synthetic is True
    assert s3.random_seed == 42
    assert "MUST be labeled synthetic" in s3.governance_notes


def test_build_scenario_s2_filtering():
    """Verify that build_scenario_s2 filters strictly by TransactionDT and does not access labels."""
    df = pd.DataFrame({
        "TransactionID": [1, 2, 3, 4],
        "TransactionDT": [10500000, 11000000, 11500000, 12000000],
        "isFraud": [0, 1, 0, 1],
    })

    s2_df = build_scenario_s2(df)
    # Threshold is 11,315,422 -> Transactions 3 and 4 should be retained
    assert len(s2_df) == 2
    assert list(s2_df["TransactionID"]) == [3, 4]
    assert all(s2_df["TransactionDT"] >= 11315422)


def test_build_scenario_s3_synthetic_perturbation():
    """Verify that S3 perturbation applies deterministic modification and preserves metadata."""
    df = pd.DataFrame({
        "TransactionID": [1, 2, 3],
        "TransactionDT": [100, 200, 300],
        "feature_1": [10.0, 20.0, 30.0],
        "feature_2": [1.0, 2.0, 3.0],
        "isFraud": [0, 0, 1],
    })

    s3_df1 = build_scenario_s3(df, seed=42)
    s3_df2 = build_scenario_s3(df, seed=42)

    # Identical seed produces identical perturbations
    pd.testing.assert_frame_equal(s3_df1, s3_df2)

    # TransactionID, TransactionDT, and isFraud are unchanged
    assert list(s3_df1["TransactionID"]) == [1, 2, 3]
    assert list(s3_df1["TransactionDT"]) == [100, 200, 300]
    assert list(s3_df1["isFraud"]) == [0, 0, 1]

    # Features are perturbed
    assert not np.allclose(s3_df1["feature_1"], df["feature_1"])
    assert s3_df1.attrs.get("scenario") == "S3_SYNTHETIC"
    assert s3_df1.attrs.get("seed") == 42


def test_export_scenario_manifest(tmp_path: Path):
    """Verify scenario manifest export to JSON."""
    out_file = tmp_path / "test_manifest.json"
    manifest = export_scenario_manifest(out_file)

    assert out_file.exists()
    loaded = json.loads(out_file.read_text(encoding="utf-8"))
    assert "scenarios" in loaded
    assert set(loaded["scenarios"].keys()) == {"S0", "S1", "S2", "S3"}
