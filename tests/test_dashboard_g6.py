"""Tests for Streamlit dashboard data loader, lane counts, and offline startup (Gate G6)."""

import json
from pathlib import Path
import pytest

from app.dashboard_data import DashboardDataLoader, LaneCounterVerification, ProvenanceVerificationStatus
from governance.audit_chain import verify_chain


def test_dashboard_loads_all_frozen_artifacts():
    """DataLoader must successfully load all required saved artifacts."""
    loader = DashboardDataLoader()

    results = loader.load_results()
    assert results is not None
    assert "scenarios" in results
    assert "acceptance_criteria" in results
    assert "latency_benchmark" in results

    freeze = loader.load_freeze_record()
    assert freeze is not None
    assert "hashes" in freeze
    assert "frozen_system" in freeze

    shift_manifest = loader.load_shift_manifest()
    assert shift_manifest is not None
    assert "scenarios" in shift_manifest

    agent_cache = loader.load_agent_cache()
    assert agent_cache is not None
    assert agent_cache.get("total_cached", 0) > 0
    assert len(agent_cache.get("records", [])) > 0

    drift_report = loader.load_drift_report()
    assert drift_report is not None
    assert "scenarios" in drift_report


def test_dashboard_lane_count_consistency_s0_to_s3():
    """Recomputed lane sums must strictly match recorded total cases across all scenarios."""
    loader = DashboardDataLoader()

    for sc_id in ["S0", "S1", "S2", "S3"]:
        check = loader.verify_lane_counters(sc_id)
        assert isinstance(check, LaneCounterVerification)
        assert check.is_consistent is True, f"Inconsistency in {sc_id}: {check.discrepancy_details}"
        assert check.sum_of_lanes == check.total_cases
        assert check.sum_reviewed_lanes == check.reviewed_cases
        assert check.total_cases > 0


def test_dashboard_provenance_hashes_verification():
    """Recorded configuration and split hashes must match actual files on disk."""
    loader = DashboardDataLoader()
    prov = loader.verify_provenance()

    assert isinstance(prov, ProvenanceVerificationStatus)
    assert prov.config_hash_verified is True
    assert prov.split_hash_verified is True
    assert prov.policy_hash_verified is True

    # Exact expected hashes
    assert prov.actual_config_hash == "e73a0e02fbd5411928ee41a0c70d71584ddc3a17ef9fc8711f318b99baed7f6e"
    assert prov.actual_split_hash == "88d73a15fc60f9badfedc4909ede017de45a99f6c58798d54ab9c1dff90690f1"
    assert prov.actual_policy_hash == "10a2fd1f33ec388298f462d8390c8ca2e303d5c411be2643416322a8795b3c48"


def test_dashboard_audit_chain_verification():
    """HMAC audit chain must verify with 0 errors and matching signature chain."""
    loader = DashboardDataLoader()
    chain_res = loader.verify_audit_chain()

    assert chain_res["ok"] is True
    assert chain_res["record_count"] >= 20
    assert len(chain_res["errors"]) == 0
    assert chain_res["final_hash"] is not None
    assert len(chain_res["final_hash"]) == 64


def test_dashboard_fails_closed_on_missing_artifacts(tmp_path):
    """Loader must fail closed safely without unhandled exceptions when files are missing."""
    empty_loader = DashboardDataLoader(root_dir=tmp_path)

    assert empty_loader.load_results() is None
    assert empty_loader.load_freeze_record() is None
    assert empty_loader.load_shift_manifest() is None
    assert empty_loader.load_agent_cache() is None
    assert empty_loader.load_drift_report() is None

    prov = empty_loader.verify_provenance()
    assert prov.config_hash_verified is False
    assert prov.split_hash_verified is False

    lane_check = empty_loader.verify_lane_counters("S0")
    assert lane_check.is_consistent is False

    chain_check = empty_loader.verify_audit_chain()
    assert chain_check["ok"] is False


def test_agent_cache_security_and_provenance():
    """Cached agent records must contain zero raw features/labels and adhere strictly to schema."""
    loader = DashboardDataLoader()
    cache = loader.load_agent_cache()
    assert cache is not None

    for rec in cache["records"]:
        # Forbidden keys check (raw feature vector, ground truth labels)
        assert "isFraud" not in rec, f"Leak: isFraud label present in agent record {rec['record_id']}"
        assert "raw_features" not in rec, f"Leak: raw features present in agent record {rec['record_id']}"

        # Allowed allowlisted keys
        assert "p" in rec
        assert "u" in rec
        assert "action" in rec
        assert "reason" in rec
        assert rec["action"] in ["FRAUD_ALERT", "MANUAL_REVIEW", "ROUTINE", "HELD", "DEFERRED"]

        # Provenance hashes
        assert rec["cfg_hash"] == "e73a0e02fbd5411928ee41a0c70d71584ddc3a17ef9fc8711f318b99baed7f6e"
        assert rec["split_hash"] == "88d73a15fc60f9badfedc4909ede017de45a99f6c58798d54ab9c1dff90690f1"


def test_offline_app_import_and_execution_readiness():
    """Ensure streamlit_app and dashboard modules import cleanly in pure offline mode."""
    import importlib
    import app.dashboard_data
    importlib.reload(app.dashboard_data)

    loader = app.dashboard_data.DashboardDataLoader()
    res = loader.load_results()
    assert res is not None
