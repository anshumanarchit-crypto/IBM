"""Case Copilot agent implementation for SignalGate Gate G3.

Provides analyst decision-support briefs for escalated cases:
  - FRAUD_ALERT
  - MANUAL_REVIEW
  - HELD / DEFERRED

Security Invariants:
1. Ingests ONLY AgentCaseView records; rejects raw features, datasets, or label containers.
2. Returns typed AgentRecord containing only verified claims and provenance hashes.
3. Every proposed claim is validated deterministically via ClaimVerifier.
4. Preserves a clean offline / mock mode when external LLM providers are unavailable.
5. Failures or timeouts NEVER modify deterministic routing action or reason code.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Callable

from agents.claim_verifier import ClaimVerifier
from schemas.agent_view import AgentCaseView
from schemas.contracts import AgentRecord, Claim
from security.tee_policy import (
    AttestationEvidence,
    ExecutionAuthorization,
    authorize_protected_execution,
)


def _canonical_bytes(obj: Any) -> bytes:
    """Serialize object to canonical JSON bytes for deterministic hashing."""
    if hasattr(obj, "model_dump"):
        data = obj.model_dump(mode="json")
    elif isinstance(obj, dict):
        data = obj
    else:
        data = {"value": str(obj)}
    text = json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return text.encode("utf-8")


class CaseCopilot:
    """Decision-support copilot operating strictly within the AgentView boundary."""

    def __init__(
        self,
        verifier: ClaimVerifier | None = None,
        llm_provider: Callable[[AgentCaseView], list[Claim]] | None = None,
        timeout_seconds: float = 5.0,
        require_attestation: bool = False,
        attestation_evidence: AttestationEvidence | None = None,
    ) -> None:
        self.verifier = verifier or ClaimVerifier()
        self.llm_provider = llm_provider
        self.timeout_seconds = timeout_seconds
        self.require_attestation = require_attestation
        self.attestation_evidence = attestation_evidence

    def generate_brief(self, case_view: AgentCaseView) -> AgentRecord:
        """Generate a verified decision-support record for one case view."""
        # 1. Fail closed if input is not an AgentCaseView
        if not isinstance(case_view, AgentCaseView):
            raise TypeError(
                "Prohibited input: CaseCopilot requires AgentCaseView, "
                f"got {type(case_view).__name__}"
            )

        # 2. Enforce configured attestation policy before invoking any provider.
        authorization: ExecutionAuthorization = authorize_protected_execution(
            self.attestation_evidence,
            require_attestation=self.require_attestation,
        )
        if not authorization.allowed:
            raise PermissionError(authorization.reason)

        # Compute input provenance hash
        input_hash = hashlib.sha256(_canonical_bytes(case_view)).hexdigest()

        # 2. Check provider availability
        if self.llm_provider is None:
            # Deterministic offline mock provider generating legitimate proposals
            raw_claims = self._generate_offline_claims(case_view)
        else:
            try:
                raw_claims = self.llm_provider(case_view)
            except TimeoutError:
                return AgentRecord(
                    agent_id="case_copilot",
                    record_id=case_view.record_id,
                    status="timed_out",
                    claims=[],
                    input_hash=input_hash,
                    cfg_hash=case_view.cfg_hash,
                    output_hash=None,
                    timestamp=datetime.now(timezone.utc),
                )
            except Exception:
                return AgentRecord(
                    agent_id="case_copilot",
                    record_id=case_view.record_id,
                    status="failed",
                    claims=[],
                    input_hash=input_hash,
                    cfg_hash=case_view.cfg_hash,
                    output_hash=None,
                    timestamp=datetime.now(timezone.utc),
                )

        # 3. Deterministic claim verification
        verified_claims, _, _ = self.verifier.verify_all(raw_claims, case_view)

        # Compute output provenance hash
        claims_bytes = _canonical_bytes([c.model_dump(mode="json") for c in verified_claims])
        output_hash = hashlib.sha256(claims_bytes).hexdigest()

        return AgentRecord(
            agent_id="case_copilot",
            record_id=case_view.record_id,
            status="ok",
            claims=verified_claims,
            input_hash=input_hash,
            cfg_hash=case_view.cfg_hash,
            output_hash=output_hash,
            timestamp=datetime.now(timezone.utc),
        )

    def _generate_offline_claims(self, case_view: AgentCaseView) -> list[Claim]:
        """Propose verifiable claims deterministically for offline / test environments."""
        claims: list[Claim] = []

        # Claim 1: Calibrated risk statement
        if case_view.p is not None:
            claims.append(
                Claim(
                    field="p",
                    operator="eq",
                    value=round(case_view.p, 4),
                    template_id="T1_CALIBRATED_RISK",
                )
            )

        # Claim 2: Model disagreement statement
        if case_view.u is not None:
            claims.append(
                Claim(
                    field="u",
                    operator="eq",
                    value=round(case_view.u, 4),
                    template_id="T2_MODEL_DISAGREEMENT",
                )
            )

        # Claim 3: Routing action and reason
        claims.append(
            Claim(
                field="action",
                operator="eq",
                value=case_view.action,
                template_id="T3_ROUTING_ACTION",
            )
        )

        # Claim 4: Provenance hash verification
        claims.append(
            Claim(
                field="cfg_hash",
                operator="eq",
                value=case_view.cfg_hash,
                template_id="T8_RECORD_PROVENANCE",
            )
        )

        return claims
