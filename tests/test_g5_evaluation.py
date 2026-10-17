"""Audit and governance tests for Gate G5 evaluation protocol."""

import json
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[1]
RESULTS_DIR = ROOT / "results"
FREEZE_RECORD_PATH = RESULTS_DIR / "pre_eval_freeze_record.json"
MANIFEST_PATH = RESULTS_DIR / "shift_scenarios_manifest.json"


def test_freeze_record_integrity():
    """Verify that the pre-evaluation freeze record exists and has valid structure."""
    assert FREEZE_RECORD_PATH.exists(), "pre_eval_freeze_record.json must exist"

    record = json.loads(FREEZE_RECORD_PATH.read_text(encoding="utf-8"))
    assert "frozen_system" in record
    assert "hashes" in record
    assert "scenarios" in record
    assert "statistical_protocol" in record
    assert "acceptance_criteria_rules" in record

    # Hashes check
    hashes = record["hashes"]
    assert len(hashes["config_yaml_sha256"]) == 64
    assert len(hashes["split_manifest_file_sha256"]) == 64
    assert len(hashes["train_split_hash"]) == 64
    assert len(hashes["calibration_split_hash"]) == 64
    assert len(hashes["validation_split_hash"]) == 64
    assert len(hashes["test_split_hash"]) == 64

    # Candidate Policy check
    policy_spec = record["frozen_system"]["candidate_policy"]
    assert policy_spec["disagreement_weight_lambda"] == 0.0
    assert policy_spec["budget_multiple"] == 1.5


def test_shift_scenarios_governance_consistency():
    """Verify scenarios declared in manifest match freeze record."""
    assert MANIFEST_PATH.exists(), "shift_scenarios_manifest.json must exist"

    freeze = json.loads(FREEZE_RECORD_PATH.read_text(encoding="utf-8"))
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))

    manifest_scenarios = manifest["scenarios"]
    freeze_scenarios = freeze["scenarios"]

    for sid in ["S0", "S1", "S2", "S3"]:
        assert sid in manifest_scenarios
        assert sid in freeze_scenarios
        assert manifest_scenarios[sid]["source_partition"] == freeze_scenarios[sid]["partition"]


def test_acceptance_criteria_definitions_frozen():
    """Verify that AC1-AC5 retain their exact frozen definitions."""
    freeze = json.loads(FREEZE_RECORD_PATH.read_text(encoding="utf-8"))
    ac = freeze["acceptance_criteria_rules"]

    assert "+2.0" in ac["AC1"]
    assert "10%" in ac["AC2"]
    assert "S0, S1, S2, S3" in ac["AC3"]
    assert "10%" in ac["AC4"]
    assert "50.0 ms" in ac["AC5"]


def test_workload_formula_invariant():
    """Verify official workload formula definition."""
    freeze = json.loads(FREEZE_RECORD_PATH.read_text(encoding="utf-8"))
    workload = freeze["workload_and_budget"]

    assert workload["official_workload_formula"] == "(FRAUD_ALERT + MANUAL_REVIEW) / N"
    assert "HELD/DEFERRED" in workload["deferred_treatment"]
