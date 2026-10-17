"""Tests for deterministic ReplayGate and Human-in-the-Loop governance (Gate G4)."""

import numpy as np
import pytest

from governance.replay_gate import ReplayEvaluationRecord, ReplayGate
from schemas.contracts import Proposal

FROZEN_BASE_HASH = "10a2fd1f33ec388298f462d8390c8ca2e303d5c411be2643416322a8795b3c48"


@pytest.fixture
def sample_validation_data():
    """Create reproducible synthetic validation partition data."""
    rng = np.random.RandomState(42)
    n = 2000
    # Simulate risk scores and ground truth
    scores = rng.beta(a=0.5, b=10, size=n)
    tx_ids = np.arange(100000, 100000 + n)
    # 3.5% prevalence
    labels = np.zeros(n, dtype=np.int32)
    fraud_indices = rng.choice(n, size=70, replace=False)
    labels[fraud_indices] = 1

    train_prevalence = 0.0338
    return scores, tx_ids, labels, train_prevalence


def test_replay_gate_rejects_base_hash_mismatch(sample_validation_data):
    """Proposals referencing an obsolete or fabricated base hash must be rejected immediately."""
    scores, tx_ids, labels, prev = sample_validation_data
    gate = ReplayGate(frozen_cfg_hash=FROZEN_BASE_HASH)

    bad_hash_proposal = Proposal(
        proposal_id="prop_bad_hash",
        base_cfg_hash="0" * 64,  # Mismatched base hash
        changes={"budget.primary_multiple": 2.0},
        rationale="Attempt with obsolete base hash",
    )

    record = gate.replay(bad_hash_proposal, scores, tx_ids, labels, prev)
    assert isinstance(record, ReplayEvaluationRecord)
    assert record.status == "REJECTED"
    assert record.hash_matched is False
    assert any("Base configuration hash mismatch" in r for r in record.rejection_reasons)


def test_replay_gate_rejects_forbidden_keys(sample_validation_data):
    """Proposals with unallowlisted keys must be rejected before replay."""
    scores, tx_ids, labels, prev = sample_validation_data
    gate = ReplayGate(frozen_cfg_hash=FROZEN_BASE_HASH)

    forbidden_key_proposal = Proposal(
        proposal_id="prop_forbidden_key",
        base_cfg_hash=FROZEN_BASE_HASH,
        changes={"model.retrain_dataset": "custom_dataset.csv"},
        rationale="Unallowlisted key attempt",
    )

    record = gate.replay(forbidden_key_proposal, scores, tx_ids, labels, prev)
    assert record.status == "REJECTED"
    assert record.keys_valid is False
    assert any("Forbidden configuration key" in r for r in record.rejection_reasons)


def test_replay_gate_rejects_excessive_workload(sample_validation_data):
    """Proposals requesting review budget beyond maximum workload constraints must fail."""
    scores, tx_ids, labels, prev = sample_validation_data
    gate = ReplayGate(frozen_cfg_hash=FROZEN_BASE_HASH, max_workload_multiple=3.0)

    excessive_proposal = Proposal(
        proposal_id="prop_excessive_workload",
        base_cfg_hash=FROZEN_BASE_HASH,
        changes={"budget.primary_multiple": 5.0},  # Exceeds max 3.0
        rationale="Requesting excessive review multiple",
    )

    record = gate.replay(excessive_proposal, scores, tx_ids, labels, prev)
    assert record.status == "REJECTED"
    assert any("exceeds permissible workload bounds" in r for r in record.rejection_reasons)


def test_replay_gate_valid_proposal_awaits_human_approval(sample_validation_data):
    """A valid proposal passing replay transitions to AWAITING_HUMAN_APPROVAL, NEVER auto-active."""
    scores, tx_ids, labels, prev = sample_validation_data
    gate = ReplayGate(frozen_cfg_hash=FROZEN_BASE_HASH)

    valid_proposal = Proposal(
        proposal_id="prop_valid_expansion",
        base_cfg_hash=FROZEN_BASE_HASH,
        changes={"budget.primary_multiple": 2.0},
        rationale="Increase budget from 1.5x to 2.0x during shift",
    )

    record = gate.replay(valid_proposal, scores, tx_ids, labels, prev)

    assert record.status == "AWAITING_HUMAN_APPROVAL"
    assert record.validation_passed is True
    assert record.workload_constraint_passed is True
    assert record.baseline_metrics["budget_multiple"] == 1.5
    assert record.proposed_metrics["budget_multiple"] == 2.0
    assert record.approved_by is None
    assert record.approval_timestamp is None
    assert record.record_hash != "0" * 64


def test_human_in_the_loop_approval_workflow(sample_validation_data):
    """Enforce that approval requires explicit human sign-off and cannot approve rejected proposals."""
    scores, tx_ids, labels, prev = sample_validation_data
    gate = ReplayGate(frozen_cfg_hash=FROZEN_BASE_HASH)

    valid_proposal = Proposal(
        proposal_id="prop_hil_01",
        base_cfg_hash=FROZEN_BASE_HASH,
        changes={"budget.primary_multiple": 2.0},
        rationale="Valid proposal for HIL test",
    )
    record = gate.replay(valid_proposal, scores, tx_ids, labels, prev)
    assert record.status == "AWAITING_HUMAN_APPROVAL"

    # Human sign-off applied
    approved_record = gate.apply_human_approval(
        record,
        approver_id="analyst_402",
        approver_role="ChiefRiskOfficer",
    )
    assert approved_record.status == "APPROVED_ACTIVE"
    assert approved_record.approved_by == "ChiefRiskOfficer:analyst_402"
    assert approved_record.approval_timestamp is not None
    assert approved_record.record_hash != record.record_hash

    # Cannot approve rejected records
    rejected_proposal = Proposal(
        proposal_id="prop_hil_fail",
        base_cfg_hash="0" * 64,
        changes={"budget.primary_multiple": 2.0},
        rationale="Bad hash",
    )
    rejected_record = gate.replay(rejected_proposal, scores, tx_ids, labels, prev)
    with pytest.raises(ValueError, match="Cannot approve proposal with status 'REJECTED'"):
        gate.apply_human_approval(
            rejected_record,
            approver_id="analyst_402",
            approver_role="ChiefRiskOfficer",
        )
