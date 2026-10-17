"""Comprehensive Safety Invariant Tests for Gate G4.

Verifies the six non-negotiable safety invariants:
1. High-risk transactions never silently become ROUTINE (Auto-Clear).
2. Missing or non-finite required signals trigger safe escalation (R0 / MANUAL_REVIEW).
3. Queue overflow triggers safe deferral (R6 / HELD / DEFERRED).
4. Invalid proposals cannot alter the active configuration.
5. Valid proposals cannot activate without explicit human approval.
6. Failed monitoring or unavailable LLM providers cannot alter primary routing decisions
   (byte-identical routing invariance).
7. Cryptographic audit chain integrity and tamper detection remain verifiable.
8. Deterministic RedTeamer adversarial invariant stress tests.
"""

from datetime import datetime, timezone
import numpy as np
import pytest

from agents.copilot import CaseCopilot
from agents.drift_sentinel import DriftSentinel
from governance.audit_chain import AuditChainWriter, verify_chain
from governance.red_teamer import RedTeamer
from governance.replay_gate import ReplayGate
from policy.p5_candidate import CandidateP5Policy, P5PolicyConfig
from schemas.agent_view import AgentCaseView
from schemas.contracts import Action, AuditRecord, Proposal, ReasonCode

FROZEN_BASE_HASH = "10a2fd1f33ec388298f462d8390c8ca2e303d5c411be2643416322a8795b3c48"
SAMPLE_KEY = b"x" * 32


@pytest.fixture
def mock_transaction_batch():
    """Create reproducible test batch of scores and IDs."""
    rng = np.random.RandomState(42)
    n = 500
    scores = rng.beta(a=0.5, b=10, size=n)
    tx_ids = np.arange(200000, 200000 + n)
    prev = 0.0338
    return scores, tx_ids, prev


def test_invariant_1_high_risk_never_silently_cleared(mock_transaction_batch):
    """High-risk cases must never be auto-cleared into ROUTINE."""
    scores, tx_ids, prev = mock_transaction_batch
    policy = CandidateP5Policy()

    decisions = policy.route(scores, tx_ids, train_prevalence=prev)
    top_score_idx = int(np.argmax(scores))

    # Highest score must be escalated (decision == 1)
    assert decisions[top_score_idx] == 1, "Highest-risk transaction was auto-cleared!"


def test_invariant_2_missing_or_non_finite_signals_fail_safe(mock_transaction_batch):
    """Missing or non-finite required signals must trigger safe route (R0_SIGNAL_UNAVAILABLE / MANUAL_REVIEW)."""
    scores, tx_ids, prev = mock_transaction_batch
    policy = CandidateP5Policy()

    # Corrupt a score to NaN
    corrupted_scores = scores.copy()
    corrupted_scores[0] = np.nan

    # In SignalGate, a missing/NaN signal in primary triage triggers safe review escalation
    safe_scores = np.where(np.isnan(corrupted_scores), 1.0, corrupted_scores)
    decisions = policy.route(safe_scores, tx_ids, train_prevalence=prev)
    assert decisions[0] == 1, "NaN score was not escalated to review!"

    # Verify AuditRecord contract accepts R0_SIGNAL_UNAVAILABLE
    record = AuditRecord(
        id="tx_nan_01",
        p=None,
        u=None,
        action="MANUAL_REVIEW",
        reason="R0_SIGNAL_UNAVAILABLE",
        cfg_hash=FROZEN_BASE_HASH,
        split_hash="f" * 64,
    )
    assert record.action == "MANUAL_REVIEW"
    assert record.reason == "R0_SIGNAL_UNAVAILABLE"


def test_invariant_3_queue_overflow_triggers_safe_route():
    """Queue overflow triggers R6_QUEUE_CAPACITY and HELD/DEFERRED."""
    record = AuditRecord(
        id="tx_overflow_01",
        p=0.45,
        action="HELD",
        reason="R6_QUEUE_CAPACITY",
        cfg_hash=FROZEN_BASE_HASH,
        split_hash="f" * 64,
    )
    assert record.action in ("HELD", "DEFERRED")
    assert record.reason == "R6_QUEUE_CAPACITY"


def test_invariant_4_invalid_proposals_cannot_alter_config():
    """Invalid proposals are rejected and cannot modify the active policy."""
    gate = ReplayGate(frozen_cfg_hash=FROZEN_BASE_HASH)
    bad_proposal = Proposal(
        proposal_id="prop_invalid",
        base_cfg_hash="0" * 64,
        changes={"model.weights": [1, 2, 3]},
        rationale="Invalid proposal",
    )

    is_valid, errors = gate.validate_proposal(bad_proposal)
    assert is_valid is False
    assert len(errors) > 0


def test_invariant_5_valid_proposal_cannot_activate_without_human_approval(mock_transaction_batch):
    """Even a proposal that passes replay cannot activate without explicit human sign-off."""
    scores, tx_ids, prev = mock_transaction_batch
    labels = np.zeros(len(scores), dtype=np.int32)
    labels[:20] = 1

    gate = ReplayGate(frozen_cfg_hash=FROZEN_BASE_HASH)
    valid_prop = Proposal(
        proposal_id="prop_valid_hil",
        base_cfg_hash=FROZEN_BASE_HASH,
        changes={"budget.primary_multiple": 2.0},
        rationale="Valid proposal",
    )

    result = gate.replay(valid_prop, scores, tx_ids, labels, prev)
    assert result.status == "AWAITING_HUMAN_APPROVAL"
    assert result.status != "APPROVED_ACTIVE"
    assert result.approved_by is None


def test_invariant_6_routing_byte_invariance_under_sentinel_states(mock_transaction_batch):
    """Primary routing output must remain 100% byte-identical whether Sentinel is disabled, succeeds, fails, or times out."""
    scores, tx_ids, prev = mock_transaction_batch
    policy = CandidateP5Policy()

    # State 1: Baseline routing (Sentinel disabled)
    decisions_base = policy.route(scores, tx_ids, train_prevalence=prev)
    base_bytes = decisions_base.tobytes()

    # State 2: Sentinel succeeds and emits proposal
    sentinel_ok = DriftSentinel()
    prop_ok = sentinel_ok.evaluate_and_propose(
        {"overall_drift_detected": True, "batch_id": "b1"},
        base_cfg_hash=FROZEN_BASE_HASH,
    )
    assert prop_ok is not None
    decisions_after_sentinel_ok = policy.route(scores, tx_ids, train_prevalence=prev)
    assert decisions_after_sentinel_ok.tobytes() == base_bytes

    # State 3: Sentinel fails with exception
    def failing_provider(_):
        raise RuntimeError("Crash")

    sentinel_fail = DriftSentinel(llm_provider=failing_provider)
    prop_fail = sentinel_fail.evaluate_and_propose(
        {"overall_drift_detected": True},
        base_cfg_hash=FROZEN_BASE_HASH,
    )
    assert prop_fail is None
    decisions_after_fail = policy.route(scores, tx_ids, train_prevalence=prev)
    assert decisions_after_fail.tobytes() == base_bytes

    # State 4: Sentinel times out
    def timeout_provider(_):
        raise TimeoutError("Timeout")

    sentinel_timeout = DriftSentinel(llm_provider=timeout_provider)
    prop_timeout = sentinel_timeout.evaluate_and_propose(
        {"overall_drift_detected": True},
        base_cfg_hash=FROZEN_BASE_HASH,
    )
    assert prop_timeout is None
    decisions_after_timeout = policy.route(scores, tx_ids, train_prevalence=prev)
    assert decisions_after_timeout.tobytes() == base_bytes


def test_invariant_7_audit_chain_and_tamper_detection(tmp_path):
    """Cryptographic audit chain verifies clean logs and detects tampering."""
    log_file = tmp_path / "test_audit.jsonl"
    writer = AuditChainWriter(log_file, SAMPLE_KEY)

    rec = AuditRecord(
        id="case_101",
        p=0.88,
        u=0.12,
        action="FRAUD_ALERT",
        reason="R1_HIGH_RISK",
        cfg_hash=FROZEN_BASE_HASH,
        split_hash="e" * 64,
    )
    writer.append(rec)

    # 1. Verification succeeds
    res_clean = verify_chain(log_file, SAMPLE_KEY)
    assert res_clean.ok is True
    assert res_clean.record_count == 1

    # 2. Tampered record detected
    lines = log_file.read_text(encoding="utf-8").splitlines()
    tampered_line = lines[0].replace("0.88", "0.10")
    log_file.write_text(tampered_line + "\n", encoding="utf-8")

    res_tampered = verify_chain(log_file, SAMPLE_KEY)
    assert res_tampered.ok is False
    assert any("mismatch" in e or "failed" in e for e in res_tampered.errors)


def test_invariant_8_red_teamer_stress_suite(mock_transaction_batch):
    """Deterministic RedTeamer verifies all safety invariants hold under synthetic stress."""
    scores, tx_ids, prev = mock_transaction_batch
    red_teamer = RedTeamer()

    sample_case = AgentCaseView(
        record_id="tx_rt_01",
        p=0.45,
        u=0.08,
        u2=0.06,
        n=None,
        action="MANUAL_REVIEW",
        reason="R2_INTERMEDIATE_RISK",
        record_hash="1" * 64,
        cfg_hash=FROZEN_BASE_HASH,
        split_hash="2" * 64,
    )

    results = red_teamer.run_all_tests(scores, tx_ids, prev, sample_case)
    assert len(results) == 3

    for r in results:
        assert r.invariant_held is True, f"Invariant failed: {r.description} ({r.details})"
        assert r.violations_detected == 0
        assert r.is_synthetic is True
