"""Shift Scenario Specifications and Data Governance for SignalGate Gate G4.

Defines the four core evaluation and stress-testing scenarios:
- S0: Original chronological test set (118,108 rows). Historical G1 baseline preserved.
- S1: Late-period chronological scenario (TransactionDT >= 14,800,000). Defined in advance.
- S2: Constructed real-data shift (Held-out temporal slice of validation partition).
- S3: Synthetic perturbation (Controlled numerical stress test, seed=42, labeled synthetic).

Governance Invariants:
1. Ground Truth Isolation: Test labels (isFraud) are never used to construct, filter,
   or tune scenarios.
2. Leakage Prevention: S2 and S3 are constructed strictly from development/validation rows,
   preserving test-set quarantine.
3. Provenance Honesty: S3 is strictly labeled synthetic, never natural drift.
4. Historical Preservation: Prior G1 test metrics are preserved in historical records;
   no claim of 'first-ever test evaluation' is made.
5. No AC3 Claim: Constructing scenarios does NOT constitute proof that AC3 has passed.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal
import numpy as np
import pandas as pd
from pydantic import BaseModel, ConfigDict, Field

ScenarioID = Literal["S0", "S1", "S2", "S3"]

S1_LATE_PERIOD_DT_THRESHOLD = 14800000
S2_VAL_DT_THRESHOLD = 11315422
S3_DEFAULT_SEED = 42


class ShiftScenarioSpec(BaseModel):
    """Specification and governance metadata for a shift scenario."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    scenario_id: ScenarioID
    name: str = Field(min_length=1)
    description: str = Field(min_length=1)
    source_partition: str = Field(min_length=1)
    is_synthetic: bool
    random_seed: int | None = None
    dt_min: int | None = None
    dt_max: int | None = None
    expected_row_count: int | None = None
    governance_notes: str = Field(min_length=1)
    data_use_rules: str = Field(min_length=1)


SCENARIO_SPECS: dict[ScenarioID, ShiftScenarioSpec] = {
    "S0": ShiftScenarioSpec(
        scenario_id="S0",
        name="Original Chronological Test Set",
        description="Full 20% chronological test partition (118,108 transactions).",
        source_partition="test",
        is_synthetic=False,
        random_seed=None,
        dt_min=12192900,
        dt_max=15811131,
        expected_row_count=118108,
        governance_notes=(
            "Historical baseline metrics were previously recorded in Gate G1 artifacts. "
            "Preserves historical record; strictly quarantined against tuning, feature selection, "
            "or proposal ranking."
        ),
        data_use_rules="Quarantined benchmark only. Models and policies must never be tuned on S0.",
    ),
    "S1": ShiftScenarioSpec(
        scenario_id="S1",
        name="Late-Period Chronological Test Scenario",
        description=(
            "Final chronological portion of the test period defined by TransactionDT >= 14,800,000 "
            "(approximately the final 28% of the test timeline)."
        ),
        source_partition="test",
        is_synthetic=False,
        random_seed=None,
        dt_min=S1_LATE_PERIOD_DT_THRESHOLD,
        dt_max=15811131,
        expected_row_count=None,  # Defined strictly by timestamp threshold in advance
        governance_notes=(
            "Pre-registered late-period scenario testing long-horizon temporal degradation. "
            "Defined strictly in advance by time boundary, without label inspection."
        ),
        data_use_rules="Evaluated only at final system evaluation gate; zero tuning allowed.",
    ),
    "S2": ShiftScenarioSpec(
        scenario_id="S2",
        name="Constructed Real-Data Shift (Validation Window Slice)",
        description=(
            "Late chronological half of the validation partition (TransactionDT >= 11,315,422). "
            "Constructed from real transactions held out from model training and calibration."
        ),
        source_partition="validation",
        is_synthetic=False,
        random_seed=None,
        dt_min=S2_VAL_DT_THRESHOLD,
        dt_max=12192842,
        expected_row_count=29527,
        governance_notes=(
            "Constructed purely from real transactions within the permitted validation partition. "
            "Zero exposure to the test partition."
        ),
        data_use_rules="Permitted for replay gate testing, sentinel trigger validation, and threshold verification.",
    ),
    "S3": ShiftScenarioSpec(
        scenario_id="S3",
        name="Synthetic Perturbation Scenario",
        description=(
            "Controlled synthetic stress test applying deterministic feature scaling and "
            "Gaussian noise injection (seed=42) to validation partition features."
        ),
        source_partition="validation",
        is_synthetic=True,
        random_seed=S3_DEFAULT_SEED,
        dt_min=10438003,
        dt_max=12192842,
        expected_row_count=59054,
        governance_notes=(
            "Deterministic synthetic perturbation. MUST be labeled synthetic, never natural drift. "
            "Does not constitute proof of robustness against all real-world shifts."
        ),
        data_use_rules="Permitted for invariant testing, Red-Teamer evaluations, and replay verification.",
    ),
}


def get_scenario_specs() -> dict[ScenarioID, ShiftScenarioSpec]:
    """Retrieve pre-registered scenario specifications."""
    return SCENARIO_SPECS


def build_scenario_s2(validation_df: pd.DataFrame) -> pd.DataFrame:
    """Filter validation dataframe to create S2 real-data shift scenario.

    Uses strictly TransactionDT filtering, completely independent of isFraud.
    """
    if "TransactionDT" not in validation_df.columns:
        raise ValueError("DataFrame must contain 'TransactionDT'")

    s2_df = validation_df[validation_df["TransactionDT"] >= S2_VAL_DT_THRESHOLD].copy()
    return s2_df.reset_index(drop=True)


def build_scenario_s3(
    validation_df: pd.DataFrame,
    feature_columns: list[str] | None = None,
    seed: int = S3_DEFAULT_SEED,
) -> pd.DataFrame:
    """Construct synthetic perturbation scenario S3 with deterministic seed.

    Labels output as synthetic. Modifies numerical features with bounded noise and scaling.
    """
    rng = np.random.RandomState(seed)
    perturbed_df = validation_df.copy()

    cols_to_perturb = feature_columns or [
        c for c in perturbed_df.columns
        if c not in ("TransactionID", "TransactionDT", "isFraud")
        and pd.api.types.is_numeric_dtype(perturbed_df[c])
    ]

    for col in cols_to_perturb:
        if col in perturbed_df.columns:
            vals = perturbed_df[col].to_numpy(dtype=np.float64, copy=True)
            mask = np.isfinite(vals)
            if np.any(mask):
                noise = rng.normal(loc=0.0, scale=0.15 * (np.nanstd(vals) or 1.0), size=int(np.sum(mask)))
                vals[mask] = (vals[mask] * 1.15) + noise
                perturbed_df[col] = vals

    perturbed_df.attrs["scenario"] = "S3_SYNTHETIC"
    perturbed_df.attrs["seed"] = seed
    return perturbed_df


def export_scenario_manifest(out_path: Path | str) -> dict[str, Any]:
    """Export the shift scenario specifications to a JSON audit manifest."""
    path = Path(out_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    manifest = {
        "title": "SignalGate Shift Scenarios Manifest (Gate G4)",
        "scenarios": {k: v.model_dump(mode="json") for k, v in SCENARIO_SPECS.items()},
    }
    path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest
