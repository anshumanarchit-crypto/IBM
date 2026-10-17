"""Fail-closed tests for the TEE execution policy.

These tests validate policy decisions, not real hardware attestation.
"""

import pytest

from security.tee_policy import (
    AttestationEvidence,
    AttestationStatus,
    authorize_protected_execution,
)


@pytest.mark.parametrize(
    "evidence",
    [
        None,
        AttestationEvidence(AttestationStatus.UNVERIFIED),
        AttestationEvidence(AttestationStatus.UNAVAILABLE),
        AttestationEvidence(AttestationStatus.INVALID),
        AttestationEvidence(AttestationStatus.VERIFIED),
        AttestationEvidence(AttestationStatus.VERIFIED, verified_by=""),
    ],
)
def test_protected_execution_fails_closed(evidence):
    decision = authorize_protected_execution(evidence)
    assert decision.allowed is False
    assert decision.reason


def test_verified_status_with_verifier_identity_is_policy_allowed():
    # Synthetic fixture: this does not perform or prove hardware attestation.
    evidence = AttestationEvidence(
        AttestationStatus.VERIFIED,
        verified_by="synthetic-test-verifier",
    )

    decision = authorize_protected_execution(evidence)

    assert decision.allowed is True
    assert "reported verified" in decision.reason


def test_policy_can_explicitly_allow_unprotected_execution():
    decision = authorize_protected_execution(
        None,
        require_attestation=False,
    )

    assert decision.allowed is True
    assert "not attestation-protected" in decision.reason


def test_invalid_evidence_type_fails_closed():
    decision = authorize_protected_execution("VERIFIED")  # type: ignore[arg-type]

    assert decision.allowed is False
    assert "invalid type" in decision.reason
