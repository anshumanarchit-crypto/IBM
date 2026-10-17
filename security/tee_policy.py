"""Fail-closed policy for protected execution.

This module evaluates a verifier's result; it does not implement hardware
attestation. Local environment indicators and caller-supplied status strings
are not proof of attestation.
"""

from dataclasses import dataclass
from enum import Enum


class AttestationStatus(str, Enum):
    VERIFIED = "VERIFIED"
    UNVERIFIED = "UNVERIFIED"
    UNAVAILABLE = "UNAVAILABLE"
    INVALID = "INVALID"


@dataclass(frozen=True)
class AttestationEvidence:
    """Result returned by a trusted verifier integration.

    `verified_by` identifies the verifier component that produced the result.
    This data structure alone does not authenticate that component.
    """

    status: AttestationStatus
    verified_by: str | None = None


@dataclass(frozen=True)
class ExecutionAuthorization:
    allowed: bool
    reason: str


def authorize_protected_execution(
    evidence: AttestationEvidence | None,
    *,
    require_attestation: bool = True,
) -> ExecutionAuthorization:
    """Authorize execution only when required attestation is explicitly verified."""
    if not require_attestation:
        return ExecutionAuthorization(
            allowed=True,
            reason="Attestation policy disabled; execution is not attestation-protected.",
        )

    if evidence is None:
        return ExecutionAuthorization(False, "Attestation evidence is missing.")

    if not isinstance(evidence, AttestationEvidence):
        return ExecutionAuthorization(False, "Attestation evidence has an invalid type.")

    if evidence.status is not AttestationStatus.VERIFIED:
        return ExecutionAuthorization(
            False,
            f"Attestation status is {evidence.status.value}; protected execution denied.",
        )

    if not isinstance(evidence.verified_by, str) or not evidence.verified_by.strip():
        return ExecutionAuthorization(
            False,
            "Verified status lacks verifier identity; protected execution denied.",
        )

    return ExecutionAuthorization(
        True,
        f"Verifier '{evidence.verified_by}' reported verified attestation.",
    )
