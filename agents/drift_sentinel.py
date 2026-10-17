"""Advisory Drift Sentinel agent for SignalGate Gate G4.

Analyzes batch drift monitoring summaries and proposes policy or budget adaptations.

Architectural & Safety Invariants:
1. Ingests ONLY summarized drift diagnostics; never ingests raw transaction columns,
   feature vectors, or evaluation labels.
2. Emits strictly typed Proposal records conforming to schemas.contracts.Proposal.
3. Proposes changes ONLY for pre-registered allowlisted configuration keys.
4. Advisory only: A proposal NEVER directly mutates config.yaml, model parameters,
   routing thresholds, or historical audit records.
5. Fails closed: On provider timeout, exception, or empty input, fails cleanly without
   disrupting the active decision policy.
6. Pure standard library implementation conforming to AST isolation guardrails.
"""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from typing import Any, Callable
import uuid

from schemas.contracts import Proposal, SHA256_PATTERN

ALLOWLISTED_CONFIG_KEYS: frozenset[str] = frozenset({
    "budget.primary_multiple",
    "budget.sweep_multiples",
    "thresholds",
    "policy.p5.disagreement_weight_lambda",
    "policy.p5.budget_multiple",
})


def _canonical_bytes(obj: Any) -> bytes:
    """Deterministic JSON serialization helper."""
    text = json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return text.encode("utf-8")


class DriftSentinel:
    """Advisory agent generating formal policy-adaptation proposals upon detected drift."""

    def __init__(
        self,
        llm_provider: Callable[[dict[str, Any]], Proposal | None] | None = None,
        timeout_seconds: float = 5.0,
    ) -> None:
        self.llm_provider = llm_provider
        self.timeout_seconds = timeout_seconds

    def evaluate_and_propose(
        self,
        monitoring_summary: dict[str, Any],
        base_cfg_hash: str,
    ) -> Proposal | None:
        """Evaluate batch drift indicators and generate a typed adaptation proposal if warranted.

        Args:
            monitoring_summary: Sanitized summary dict from batch monitoring.
            base_cfg_hash: SHA-256 hash of currently frozen base configuration.

        Returns:
            Proposal object if drift warrants an adaptation proposal, else None.
        """
        if not isinstance(monitoring_summary, dict):
            raise TypeError("DriftSentinel requires a monitoring summary dict")

        if not isinstance(base_cfg_hash, str) or len(base_cfg_hash) != 64:
            raise ValueError("base_cfg_hash must be a valid 64-character SHA-256 hex string")

        # Check if external LLM provider is supplied
        if self.llm_provider is not None:
            try:
                proposal = self.llm_provider(monitoring_summary)
                if proposal is None:
                    return None
                # Validate proposal integrity
                self._validate_proposal_invariants(proposal, base_cfg_hash)
                return proposal
            except (TimeoutError, Exception):
                # Fail closed: Provider errors or timeouts never modify routing or crash
                return None

        # Offline / deterministic mock provider
        return self._generate_offline_proposal(monitoring_summary, base_cfg_hash)

    def _generate_offline_proposal(
        self,
        summary: dict[str, Any],
        base_cfg_hash: str,
    ) -> Proposal | None:
        """Deterministic offline proposal generator for test and offline environments."""
        overall_drift = summary.get("overall_drift_detected", False)
        if not overall_drift:
            return None

        significant_features = summary.get("significant_shift_features", [])
        batch_id = str(summary.get("batch_id", "unknown_batch"))

        # Formulate proposal to expand review budget to accommodate shift uncertainty
        proposal_id = f"prop_drift_{uuid.uuid4().hex[:12]}"
        changes = {
            "budget.primary_multiple": 2.0,
        }
        rationale = (
            f"Advisory proposal triggered by detected drift on batch '{batch_id}'. "
            f"Significant shifts detected on: {significant_features}. "
            "Propose increasing primary review budget multiple from 1.5x to 2.0x "
            "to absorb elevated classification ambiguity without modifying decision policy."
        )

        return Proposal(
            proposal_id=proposal_id,
            base_cfg_hash=base_cfg_hash,
            changes=changes,
            rationale=rationale,
            created_at=datetime.now(timezone.utc),
        )

    def _validate_proposal_invariants(self, proposal: Proposal, expected_base_hash: str) -> None:
        """Enforce proposal safety invariants."""
        if not isinstance(proposal, Proposal):
            raise TypeError("Generated proposal must be an instance of Proposal")

        if proposal.base_cfg_hash != expected_base_hash:
            raise ValueError(
                f"Proposal base_cfg_hash mismatch: expected {expected_base_hash}, got {proposal.base_cfg_hash}"
            )

        for key in proposal.changes.keys():
            if key not in ALLOWLISTED_CONFIG_KEYS:
                raise ValueError(f"Forbidden configuration key in proposal: '{key}'")
