"""Gate G3 acceptance tests: Checked-Claim Agent Layer.

Tests verify acceptance criteria AG1 through AG5:
- AG1: Seeded false claims rejected (100% block rate across 25 planted false claims).
- AG2: Honest claims accepted (false-block rate <= 0.05 on permitted claims).
- AG3: Verifier integrity (arbitrary prose, malformed schemas, and unsupported operators rejected).
- AG4: Routing invariance (primary triage outputs remain byte-identical regardless of agent state).
- AG5: Label-access rejection (passing raw features, isFraud, or dataframes fails closed).
- Agent lifecycle: timeouts, provider unavailability, and exceptions handled safely.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone

import numpy as np
import pytest
from pydantic import ValidationError

from agents.claim_verifier import ClaimVerifier, VerificationResult
from agents.copilot import CaseCopilot
from agents.supervisor import AgentSupervisor
from policy.p5_candidate import CandidateP5Policy, P5PolicyConfig
from schemas.agent_view import AgentCaseView
from schemas.contracts import Action, AgentRecord, AuditRecord, Claim, ReasonCode

TEST_CFG_HASH = "a" * 64
TEST_SPLIT_HASH = "b" * 64
TEST_REC_HASH = "c" * 64


@pytest.fixture
def sample_case_view() -> AgentCaseView:
    return AgentCaseView(
        record_id="tx_1001",
        p=0.7420,
        u=0.1250,
        u2=0.0820,
        n=7.0,
        action="MANUAL_REVIEW",
        reason="R3_MODEL_DISAGREEMENT",
        record_hash=TEST_REC_HASH,
        cfg_hash=TEST_CFG_HASH,
        split_hash=TEST_SPLIT_HASH,
    )


# ---------------------------------------------------------------------------
# AG1: Seeded False Claims Rejection (100% block rate)
# ---------------------------------------------------------------------------

def test_ag1_seeded_false_claims_rejection(sample_case_view: AgentCaseView):
    """Verifier must reject 100% of planted false claims across all failure categories."""
    verifier = ClaimVerifier()

    planted_false_claims: list[Claim] = [
        # Category 1: Fabricated risk probabilities
        Claim(field="p", operator="eq", value=0.9999, template_id="T1_CALIBRATED_RISK"),
        Claim(field="p", operator="eq", value=0.1000, template_id="T1_CALIBRATED_RISK"),
        Claim(field="p", operator="lt", value=0.5000, template_id="T1_CALIBRATED_RISK"),
        Claim(field="p", operator="gte", value=0.9000, template_id="T4_HIGH_RISK_THRESHOLD"),
        Claim(field="p", operator="lte", value=0.2000, template_id="T1_CALIBRATED_RISK"),

        # Category 2: Fabricated disagreement signals
        Claim(field="u", operator="eq", value=0.8500, template_id="T2_MODEL_DISAGREEMENT"),
        Claim(field="u", operator="lt", value=0.0100, template_id="T2_MODEL_DISAGREEMENT"),
        Claim(field="u", operator="gt", value=0.5000, template_id="T6_ELEVATED_DISAGREEMENT"),
        Claim(field="u2", operator="eq", value=0.5500, template_id="T7_ROBUST_MAD_SIGNAL"),
        Claim(field="u2", operator="gt", value=0.2000, template_id="T7_ROBUST_MAD_SIGNAL"),

        # Category 3: Fabricated actions and reasons
        Claim(field="action", operator="eq", value="ROUTINE", template_id="T3_ROUTING_ACTION"),
        Claim(field="action", operator="eq", value="FRAUD_ALERT", template_id="T3_ROUTING_ACTION"),
        Claim(field="reason", operator="eq", value="R5_LOW_RISK_RELIABLE", template_id="T3_ROUTING_ACTION"),
        Claim(field="reason", operator="eq", value="R1_HIGH_RISK", template_id="T3_ROUTING_ACTION"),
        Claim(field="action", operator="in", value=["ROUTINE", "DEFERRED"], template_id="T3_ROUTING_ACTION"),

        # Category 4: Fabricated metadata and provenance
        Claim(field="record_id", operator="eq", value="tx_9999", template_id="T1_CALIBRATED_RISK"),
        Claim(field="cfg_hash", operator="eq", value="f" * 64, template_id="T8_RECORD_PROVENANCE"),
        Claim(field="split_hash", operator="eq", value="0" * 64, template_id="T8_RECORD_PROVENANCE"),
        Claim(field="record_hash", operator="eq", value="e" * 64, template_id="T8_RECORD_PROVENANCE"),
        Claim(field="n", operator="eq", value=100.0, template_id="T9_MEMBER_COUNT"),

        # Category 5: Invalid templates and unsupported combinations
        Claim(field="p", operator="eq", value=0.7420, template_id="UNREGISTERED_TEMPLATE_99"),
        Claim(field="u", operator="eq", value=0.1250, template_id="FAKE_TEMPLATE_X"),
        Claim(field="p", operator="gt", value=0.8000, template_id="T4_HIGH_RISK_THRESHOLD"),
        Claim(field="p", operator="lte", value=0.6000, template_id="T1_CALIBRATED_RISK"),
        Claim(field="u", operator="gte", value=0.3000, template_id="T6_ELEVATED_DISAGREEMENT"),
    ]

    assert len(planted_false_claims) == 25, "Must test exactly 25 planted false claims"

    rejected_count = 0
    for claim in planted_false_claims:
        res = verifier.verify(claim, sample_case_view)
        if not res.is_verified:
            rejected_count += 1
            assert res.statement is None
            assert res.rejection_reason is not None

    block_rate = rejected_count / len(planted_false_claims)
    assert block_rate == 1.0, f"AG1 failed: expected 1.0 block rate, got {block_rate}"


# ---------------------------------------------------------------------------
# AG2: Honest Claims Acceptance (False-block rate <= 0.05)
# ---------------------------------------------------------------------------

def test_ag2_honest_claims_acceptance():
    """Honest, factually accurate claims must be verified and accepted with false-block rate <= 5%."""
    verifier = ClaimVerifier()

    # Create 20 diverse cases with corresponding true claims
    honest_test_cases = [
        (
            AgentCaseView(
                record_id=f"tx_{i}",
                p=round(0.1 * i, 4),
                u=round(0.02 * i, 4),
                u2=round(0.01 * i, 4),
                n=7.0,
                action="MANUAL_REVIEW" if i > 5 else "ROUTINE",
                reason="R2_INTERMEDIATE_RISK" if i > 5 else "R5_LOW_RISK_RELIABLE",
                record_hash=hashlib.sha256(f"rec_{i}".encode()).hexdigest(),
                cfg_hash=TEST_CFG_HASH,
                split_hash=TEST_SPLIT_HASH,
            ),
            [
                Claim(field="p", operator="eq", value=round(0.1 * i, 4), template_id="T1_CALIBRATED_RISK"),
                Claim(field="u", operator="eq", value=round(0.02 * i, 4), template_id="T2_MODEL_DISAGREEMENT"),
                Claim(field="action", operator="eq", value="MANUAL_REVIEW" if i > 5 else "ROUTINE", template_id="T3_ROUTING_ACTION"),
                Claim(field="cfg_hash", operator="eq", value=TEST_CFG_HASH, template_id="T8_RECORD_PROVENANCE"),
            ],
        )
        for i in range(1, 10)
    ]

    total_honest_claims = 0
    blocked_claims = 0

    for case_view, claims in honest_test_cases:
        for claim in claims:
            total_honest_claims += 1
            res = verifier.verify(claim, case_view)
            if not res.is_verified:
                blocked_claims += 1
            else:
                assert res.statement is not None
                assert isinstance(res.statement, str)

    false_block_rate = blocked_claims / total_honest_claims
    assert false_block_rate <= 0.05, f"AG2 failed: false block rate {false_block_rate} > 0.05"
    assert false_block_rate == 0.0, "Expected 0 false blocks on valid honest claims"


# ---------------------------------------------------------------------------
# AG3: Verifier Integrity (Extra fields, malformed schemas, arbitrary prose)
# ---------------------------------------------------------------------------

def test_ag3_verifier_integrity(sample_case_view: AgentCaseView):
    """Verifier must reject arbitrary prose, unregistered fields, and malformed schemas."""
    verifier = ClaimVerifier()

    # 1. Arbitrary prose string cannot be verified as a Claim
    res = verifier.verify("This transaction is obviously fraud", sample_case_view)  # type: ignore[arg-type]
    assert not res.is_verified
    assert "Expected Claim instance" in str(res.rejection_reason)

    # 2. Claim rejects extra fields via Pydantic model_config extra="forbid"
    with pytest.raises(ValidationError):
        Claim(
            field="p",
            operator="eq",
            value=0.7420,
            template_id="T1_CALIBRATED_RISK",
            prose="Arbitrary injected prose",  # type: ignore[call-arg]
        )

    # 3. Unsupported operator rejected
    claim_bad_op = Claim(
        field="p",
        operator="in",  # 'in' is valid in schema but not allowed for float 'p'
        value=[0.7420],
        template_id="T1_CALIBRATED_RISK",
    )
    res_bad_op = verifier.verify(claim_bad_op, sample_case_view)
    assert not res_bad_op.is_verified
    assert "Unsupported field/operator" in str(res_bad_op.rejection_reason)


# ---------------------------------------------------------------------------
# AG4: Routing Invariance (Byte-identical triage decisions across agent states)
# ---------------------------------------------------------------------------

def test_ag4_routing_invariance():
    """Primary triage decisions must be byte-identical whether agents are disabled, ok, failing, or timed out."""
    policy = CandidateP5Policy(P5PolicyConfig(budget_multiple=1.5))

    n_samples = 100
    p_scores = np.linspace(0.01, 0.99, n_samples)
    u_signals = np.full(n_samples, 0.08)
    tx_ids = np.array([f"TX_{i:04d}" for i in range(n_samples)])
    train_prevalence = 0.0338

    # Condition 1: Primary baseline routing (agents disabled)
    decisions_base = policy.route(p_scores, tx_ids, train_prevalence)

    # Mock agent simulation on the same transactions
    def mock_successful_copilot(cv: AgentCaseView) -> list[Claim]:
        return [Claim(field="p", operator="eq", value=round(cv.p, 4), template_id="T1_CALIBRATED_RISK")]

    def mock_failing_copilot(cv: AgentCaseView) -> list[Claim]:
        raise RuntimeError("LLM service unavailable")

    def mock_timeout_copilot(cv: AgentCaseView) -> list[Claim]:
        raise TimeoutError("Provider latency limit exceeded")

    copilot_ok = CaseCopilot(llm_provider=mock_successful_copilot)
    copilot_fail = CaseCopilot(llm_provider=mock_failing_copilot)
    copilot_timeout = CaseCopilot(llm_provider=mock_timeout_copilot)

    # Condition 2: Dispatch successful copilot for escalated cases
    supervisor_ok = AgentSupervisor(copilot=copilot_ok)
    for i, dec in enumerate(decisions_base):
        cv = AgentCaseView(
            record_id=tx_ids[i],
            p=float(p_scores[i]),
            u=float(u_signals[i]),
            action="MANUAL_REVIEW" if dec == 1 else "ROUTINE",
            reason="R1_HIGH_RISK" if dec == 1 else "R5_LOW_RISK_RELIABLE",
            record_hash=TEST_REC_HASH,
            cfg_hash=TEST_CFG_HASH,
            split_hash=TEST_SPLIT_HASH,
        )
        rec = supervisor_ok.dispatch(cv)
        if dec == 1:
            assert rec is not None
            assert rec.status == "ok"
        else:
            assert rec is None  # Routine cases are not dispatched

    decisions_after_ok = policy.route(p_scores, tx_ids, train_prevalence)

    # Condition 3: Dispatch failing copilot
    supervisor_fail = AgentSupervisor(copilot=copilot_fail)
    for i, dec in enumerate(decisions_base):
        if dec == 1:
            cv = AgentCaseView(
                record_id=tx_ids[i],
                p=float(p_scores[i]),
                u=float(u_signals[i]),
                action="MANUAL_REVIEW",
                reason="R1_HIGH_RISK",
                record_hash=TEST_REC_HASH,
                cfg_hash=TEST_CFG_HASH,
                split_hash=TEST_SPLIT_HASH,
            )
            rec = supervisor_fail.dispatch(cv)
            assert rec is not None
            assert rec.status == "failed"

    decisions_after_fail = policy.route(p_scores, tx_ids, train_prevalence)

    # Condition 4: Dispatch timed-out copilot
    supervisor_timeout = AgentSupervisor(copilot=copilot_timeout)
    for i, dec in enumerate(decisions_base):
        if dec == 1:
            cv = AgentCaseView(
                record_id=tx_ids[i],
                p=float(p_scores[i]),
                u=float(u_signals[i]),
                action="MANUAL_REVIEW",
                reason="R1_HIGH_RISK",
                record_hash=TEST_REC_HASH,
                cfg_hash=TEST_CFG_HASH,
                split_hash=TEST_SPLIT_HASH,
            )
            rec = supervisor_timeout.dispatch(cv)
            assert rec is not None
            assert rec.status == "timed_out"

    decisions_after_timeout = policy.route(p_scores, tx_ids, train_prevalence)

    # Invariance check: routing outputs must be 100% byte-identical
    assert np.array_equal(decisions_base, decisions_after_ok)
    assert np.array_equal(decisions_base, decisions_after_fail)
    assert np.array_equal(decisions_base, decisions_after_timeout)


# ---------------------------------------------------------------------------
# AG5: Label-Access Rejection (Fail-closed on prohibited data objects)
# ---------------------------------------------------------------------------

def test_ag5_label_access_fails_closed():
    """Any attempt to pass forbidden labels or raw data to the copilot must fail closed."""
    copilot = CaseCopilot()

    # 1. Attempting to pass raw dict with forbidden label field
    forbidden_dict = {
        "record_id": "tx_1",
        "p": 0.8,
        "isFraud": 1,
    }
    with pytest.raises(TypeError, match="Prohibited input"):
        copilot.generate_brief(forbidden_dict)  # type: ignore[arg-type]

    # 2. Attempting to create an AgentCaseView with extra/prohibited fields
    with pytest.raises(ValidationError):
        AgentCaseView(
            record_id="tx_1",
            p=0.8,
            action="MANUAL_REVIEW",
            reason="R1_HIGH_RISK",
            record_hash=TEST_REC_HASH,
            cfg_hash=TEST_CFG_HASH,
            split_hash=TEST_SPLIT_HASH,
            isFraud=1,  # type: ignore[call-arg]
        )

    # 3. Attempting to pass raw feature name
    with pytest.raises(ValidationError):
        AgentCaseView(
            record_id="tx_1",
            p=0.8,
            action="MANUAL_REVIEW",
            reason="R1_HIGH_RISK",
            record_hash=TEST_REC_HASH,
            cfg_hash=TEST_CFG_HASH,
            split_hash=TEST_SPLIT_HASH,
            TransactionAmt=150.0,  # type: ignore[call-arg]
        )


# ---------------------------------------------------------------------------
# Lifecycle: Unavailable Provider & Supervisor Dispatch
# ---------------------------------------------------------------------------

def test_copilot_offline_mode(sample_case_view: AgentCaseView):
    """Offline mode generates verified claims without external provider dependencies."""
    copilot = CaseCopilot(llm_provider=None)
    rec = copilot.generate_brief(sample_case_view)
    assert rec.status == "ok"
    assert len(rec.claims) >= 3
    assert rec.input_hash is not None
    assert rec.output_hash is not None
    assert rec.record_id == sample_case_view.record_id


def test_supervisor_routine_ineligibility():
    """Routine cases are ineligible for agent dispatch."""
    supervisor = AgentSupervisor()
    routine_case = AgentCaseView(
        record_id="tx_routine",
        p=0.01,
        u=0.01,
        action="ROUTINE",
        reason="R5_LOW_RISK_RELIABLE",
        record_hash=TEST_REC_HASH,
        cfg_hash=TEST_CFG_HASH,
        split_hash=TEST_SPLIT_HASH,
    )
    assert not supervisor.is_eligible(routine_case)
    assert supervisor.dispatch(routine_case) is None


def test_copilot_denies_provider_without_attestation(sample_case_view: AgentCaseView):
    """Required attestation denies execution before the configured provider runs."""
    provider_called = False

    def provider(cv: AgentCaseView) -> list[Claim]:
        nonlocal provider_called
        provider_called = True
        return []

    copilot = CaseCopilot(
        llm_provider=provider,
        require_attestation=True,
        attestation_evidence=None,
    )

    with pytest.raises(PermissionError, match="Attestation evidence is missing"):
        copilot.generate_brief(sample_case_view)

    assert provider_called is False
