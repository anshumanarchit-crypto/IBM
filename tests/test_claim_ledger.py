"""Tests for deterministic Claim Ledger and Evidence Classification (Gate G6)."""

import json
from pathlib import Path
import pytest

from governance.claim_ledger import (
    ClaimLedger,
    LedgerVerificationResult,
    ReportableClaim,
)

FROZEN_RESULTS_PATH = Path("results/results.json")
FREEZE_RECORD_PATH = Path("results/pre_eval_freeze_record.json")


def test_claim_ledger_verifies_all_honest_standard_claims():
    """All 16 registered headline claims must verify deterministically against results.json."""
    ledger = ClaimLedger(results_path=FROZEN_RESULTS_PATH, freeze_record_path=FREEZE_RECORD_PATH)
    claims = ledger.build_standard_claims()
    assert len(claims) >= 15

    results, verified_cnt, rejected_cnt = ledger.verify_all(claims)
    assert rejected_cnt == 0, f"Expected 0 rejections, got {rejected_cnt}: {[r for r in results if not r.is_verified]}"
    assert verified_cnt == len(claims)

    for r in results:
        assert isinstance(r, LedgerVerificationResult)
        assert r.is_verified is True
        assert r.rejection_reason is None
        assert r.actual_value is not None


def test_claim_ledger_rejects_planted_wrong_recall():
    """Ledger must catch and deterministically reject an inflated or altered recall number."""
    ledger = ClaimLedger(results_path=FROZEN_RESULTS_PATH, freeze_record_path=FREEZE_RECORD_PATH)

    planted_claim = ReportableClaim(
        claim_id="CLM_PLANTED_S0_RECALL",
        metric_name="recall",
        scenario_id="S0",
        claimed_value=0.7500,  # Fabricated (actual is 0.513287)
        evidence_type="measured real data",
        source_artifact=str(FROZEN_RESULTS_PATH),
        sample_size=118108,
        description="Planted fabricated recall number",
    )

    res = ledger.verify_claim(planted_claim)
    assert res.is_verified is False
    assert res.actual_value == pytest.approx(0.513287, abs=1e-4)
    assert res.rejection_reason is not None
    assert "Planted or incorrect value" in res.rejection_reason
    assert "0.75" in res.rejection_reason


def test_claim_ledger_rejects_sample_size_mismatch():
    """Ledger must reject claims that cite the wrong evaluation cohort size."""
    ledger = ClaimLedger(results_path=FROZEN_RESULTS_PATH, freeze_record_path=FREEZE_RECORD_PATH)

    mismatched_claim = ReportableClaim(
        claim_id="CLM_WRONG_N",
        metric_name="sample_size",
        scenario_id="S0",
        claimed_value=118108,
        evidence_type="measured real data",
        source_artifact=str(FROZEN_RESULTS_PATH),
        sample_size=999999,  # Wrong sample size cited
        description="Claim with mismatched sample size",
    )

    res = ledger.verify_claim(mismatched_claim)
    assert res.is_verified is False
    assert "Sample size mismatch" in (res.rejection_reason or "")


def test_claim_ledger_rejects_config_hash_mismatch():
    """Ledger must reject claims citing an obsolete or fabricated configuration hash."""
    ledger = ClaimLedger(results_path=FROZEN_RESULTS_PATH, freeze_record_path=FREEZE_RECORD_PATH)

    bad_hash_claim = ReportableClaim(
        claim_id="CLM_BAD_CONFIG_HASH",
        metric_name="recall",
        scenario_id="S0",
        claimed_value=0.513287,
        evidence_type="measured real data",
        source_artifact=str(FROZEN_RESULTS_PATH),
        sample_size=118108,
        config_hash="0" * 64,  # Fabricated config hash
        description="Claim with invalid configuration hash",
    )

    res = ledger.verify_claim(bad_hash_claim)
    assert res.is_verified is False
    assert "Config hash mismatch" in (res.rejection_reason or "")


def test_claim_ledger_rejects_missing_metric_or_scenario():
    """Ledger must fail closed when requested metric or scenario does not exist."""
    ledger = ClaimLedger(results_path=FROZEN_RESULTS_PATH, freeze_record_path=FREEZE_RECORD_PATH)

    missing_metric_claim = ReportableClaim(
        claim_id="CLM_NONEXISTENT",
        metric_name="nonexistent_fraud_metric",
        scenario_id="S0",
        claimed_value=0.50,
        evidence_type="measured real data",
        source_artifact=str(FROZEN_RESULTS_PATH),
        description="Query for imaginary metric",
    )

    res = ledger.verify_claim(missing_metric_claim)
    assert res.is_verified is False
    assert "not found for scenario" in (res.rejection_reason or "")


def test_claim_ledger_rejects_missing_source_artifact(tmp_path):
    """Ledger must reject claims citing a missing source artifact file."""
    ledger = ClaimLedger(results_path=FROZEN_RESULTS_PATH, freeze_record_path=FREEZE_RECORD_PATH)

    missing_file = tmp_path / "nonexistent_results.json"
    missing_art_claim = ReportableClaim(
        claim_id="CLM_MISSING_FILE",
        metric_name="recall",
        scenario_id="S0",
        claimed_value=0.513287,
        evidence_type="measured real data",
        source_artifact=str(missing_file),
        description="Claim with missing source artifact",
    )

    res = ledger.verify_claim(missing_art_claim)
    assert res.is_verified is False
    assert "Source artifact not found" in (res.rejection_reason or "")


def test_claim_ledger_evidence_classification_types():
    """Evidence types must strictly conform to allowlisted classifications."""
    valid_types = [
        "measured real data",
        "measured synthetic data",
        "assumption",
        "planned work",
        "unavailable evidence",
        "inconclusive findings",
    ]

    for ev_type in valid_types:
        claim = ReportableClaim(
            claim_id=f"CLM_{ev_type.replace(' ', '_')}",
            metric_name="sample_size",
            scenario_id="S0",
            claimed_value=118108,
            evidence_type=ev_type,  # type: ignore[arg-type]
            source_artifact=str(FROZEN_RESULTS_PATH),
            description="Testing evidence types",
        )
        assert claim.evidence_type == ev_type

    with pytest.raises(Exception):
        ReportableClaim(
            claim_id="CLM_INVALID_EV",
            metric_name="sample_size",
            scenario_id="S0",
            claimed_value=118108,
            evidence_type="unvalidated_guess",  # type: ignore[arg-type]
            source_artifact=str(FROZEN_RESULTS_PATH),
            description="Invalid evidence classification",
        )
