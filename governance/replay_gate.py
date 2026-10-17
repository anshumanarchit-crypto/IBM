"""Deterministic Proposal Replay Gate for SignalGate Gate G4.

Enforces human-in-the-loop governance for all policy or configuration change proposals.

Architectural & Safety Invariants:
1. Strict schema & allowlist validation: Rejects unknown keys, malformed values,
   unsupported changes, or mismatched base configuration hashes.
2. Isolated validation replay: Replays proposals strictly on permitted development
   and validation partitions. NEVER uses held-out test data or test labels.
3. Workload & capacity verification: Verifies review capacity constraints and declared
   acceptance criteria before a proposal can be considered.
4. Human-in-the-Loop invariant: Passing validation replay DOES NOT automatically alter
   the operational configuration. Every activation requires explicit human sign-off.
5. Complete audit provenance: Emits immutable, hash-verified before-and-after evidence
   records documenting metrics, configuration hashes, and approval disposition.
6. Fail-closed resilience: Missing, malformed, or timed-out proposals leave the active
   frozen policy completely intact.
"""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from typing import Any, Literal
import numpy as np
from pydantic import BaseModel, ConfigDict, Field, field_validator

from agents.drift_sentinel import ALLOWLISTED_CONFIG_KEYS
from schemas.contracts import Proposal, SHA256_PATTERN, ZERO_HASH

ProposalReplayStatus = Literal["REJECTED", "AWAITING_HUMAN_APPROVAL", "APPROVED_ACTIVE"]


def _canonical_json_bytes(data: dict[str, Any]) -> bytes:
    """Return stable, sorted JSON bytes for deterministic hashing."""
    def _default(obj: Any) -> str:
        if isinstance(obj, datetime):
            return obj.isoformat()
        raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")

    return json.dumps(
        data,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=_default,
    ).encode("utf-8")


class ReplayEvaluationRecord(BaseModel):
    """Complete before-and-after audit evidence record for a proposal replay."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    proposal_id: str = Field(min_length=1)
    base_cfg_hash: str = Field(pattern=SHA256_PATTERN)
    target_cfg_hash: str = Field(pattern=SHA256_PATTERN)
    status: ProposalReplayStatus
    schema_valid: bool
    hash_matched: bool
    keys_valid: bool
    validation_passed: bool
    workload_constraint_passed: bool
    baseline_metrics: dict[str, Any]
    proposed_metrics: dict[str, Any]
    rejection_reasons: list[str] = Field(default_factory=list)
    approved_by: str | None = None
    approval_timestamp: datetime | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    record_hash: str = Field(default=ZERO_HASH, pattern=SHA256_PATTERN)

    @field_validator("created_at", "approval_timestamp")
    @classmethod
    def timestamps_must_be_timezone_aware(cls, value: datetime | None) -> datetime | None:
        if value is not None and (value.tzinfo is None or value.utcoffset() is None):
            raise ValueError("timestamp must include a timezone")
        return value


class ReplayGate:
    """Deterministic validation and governance gate for advisory proposals."""

    def __init__(
        self,
        frozen_cfg_hash: str,
        base_config: dict[str, Any] | None = None,
        max_workload_multiple: float = 3.0,
    ) -> None:
        if not isinstance(frozen_cfg_hash, str) or len(frozen_cfg_hash) != 64:
            raise ValueError("frozen_cfg_hash must be a 64-character SHA-256 hex string")

        self.frozen_cfg_hash = frozen_cfg_hash
        self.base_config = base_config or {
            "budget": {"primary_multiple": 1.5, "sweep_multiples": [1.0, 1.5, 2.0, 3.0]},
            "policy": {"p5": {"disagreement_weight_lambda": 0.0, "budget_multiple": 1.5}},
            "thresholds": None,
        }
        self.max_workload_multiple = max_workload_multiple

    def validate_proposal(self, proposal: Proposal) -> tuple[bool, list[str]]:
        """Validate proposal schema, base hash match, and allowlisted keys."""
        errors: list[str] = []

        if not isinstance(proposal, Proposal):
            return False, ["Input is not a valid Proposal instance"]

        # Check 1: Base configuration hash must match current frozen core
        if proposal.base_cfg_hash != self.frozen_cfg_hash:
            errors.append(
                f"Base configuration hash mismatch: proposal references {proposal.base_cfg_hash}, "
                f"current frozen core is {self.frozen_cfg_hash}"
            )

        # Check 2: All proposed changes must be strictly allowlisted
        if not proposal.changes:
            errors.append("Proposal contains no changes")

        for key, val in proposal.changes.items():
            if key not in ALLOWLISTED_CONFIG_KEYS:
                errors.append(f"Forbidden configuration key: '{key}' is not in allowlist")
                continue

            # Check domain validity
            if key in ("budget.primary_multiple", "policy.p5.budget_multiple"):
                if not isinstance(val, (int, float)) or val <= 0.0 or val > self.max_workload_multiple:
                    errors.append(
                        f"Value for '{key}' ({val}) exceeds permissible workload bounds (0.0, {self.max_workload_multiple}]"
                    )
            elif key == "policy.p5.disagreement_weight_lambda":
                if not isinstance(val, (int, float)) or val < 0.0 or val > 1.0:
                    errors.append(f"Value for '{key}' ({val}) must be in range [0.0, 1.0]")
            elif key == "budget.sweep_multiples":
                if not isinstance(val, list) or not all(isinstance(x, (int, float)) for x in val):
                    errors.append(f"Value for '{key}' must be a list of numbers")

        return len(errors) == 0, errors

    def replay(
        self,
        proposal: Proposal,
        validation_scores: np.ndarray,
        validation_tx_ids: np.ndarray,
        validation_labels: np.ndarray,
        train_prevalence: float,
    ) -> ReplayEvaluationRecord:
        """Deterministically replay proposal against validation partition.

        Args:
            proposal: The proposed adaptation.
            validation_scores: Calibrated risk scores on the validation partition.
            validation_tx_ids: Transaction identifiers on validation partition.
            validation_labels: Ground-truth isFraud labels for validation partition ONLY.
            train_prevalence: Training partition fraud prevalence.

        Returns:
            ReplayEvaluationRecord documenting replay results.
        """
        is_valid, validation_errors = self.validate_proposal(proposal)

        target_cfg = json.loads(json.dumps(self.base_config))
        target_cfg["proposed_changes"] = proposal.changes if is_valid else {}
        target_cfg_hash = hashlib.sha256(_canonical_json_bytes(target_cfg)).hexdigest()

        if not is_valid:
            record_data = {
                "proposal_id": proposal.proposal_id,
                "base_cfg_hash": proposal.base_cfg_hash,
                "target_cfg_hash": target_cfg_hash,
                "status": "REJECTED",
                "schema_valid": True,
                "hash_matched": proposal.base_cfg_hash == self.frozen_cfg_hash,
                "keys_valid": False,
                "validation_passed": False,
                "workload_constraint_passed": False,
                "baseline_metrics": {},
                "proposed_metrics": {},
                "rejection_reasons": validation_errors,
                "approved_by": None,
                "approval_timestamp": None,
                "created_at": datetime.now(timezone.utc),
                "record_hash": ZERO_HASH,
            }
            rec_bytes = _canonical_json_bytes({k: v for k, v in record_data.items() if k != "record_hash"})
            record_data["record_hash"] = hashlib.sha256(rec_bytes).hexdigest()
            return ReplayEvaluationRecord.model_validate(record_data)

        # Execute Baseline Policy Replay
        n_val = len(validation_scores)
        base_multiple = float(self.base_config.get("budget", {}).get("primary_multiple", 1.5))
        k_base = int(np.floor(base_multiple * train_prevalence * n_val))
        k_base = max(0, min(k_base, n_val))

        order = np.lexsort((validation_tx_ids, -validation_scores))
        base_selected = order[:k_base]

        val_labels = np.asarray(validation_labels, dtype=np.int32)
        total_positives = int(np.sum(val_labels == 1))

        base_detected = int(np.sum(val_labels[base_selected] == 1))
        base_recall = float(base_detected / total_positives) if total_positives > 0 else 0.0
        base_touched_rate = float(len(base_selected) / n_val) if n_val > 0 else 0.0

        baseline_metrics = {
            "budget_multiple": base_multiple,
            "touched_count": len(base_selected),
            "touched_rate": round(base_touched_rate, 4),
            "fraud_detected": base_detected,
            "total_fraud": total_positives,
            "recall": round(base_recall, 4),
        }

        # Execute Proposed Policy Replay
        prop_multiple = float(proposal.changes.get("budget.primary_multiple", base_multiple))
        k_prop = int(np.floor(prop_multiple * train_prevalence * n_val))
        k_prop = max(0, min(k_prop, n_val))

        prop_selected = order[:k_prop]
        prop_detected = int(np.sum(val_labels[prop_selected] == 1))
        prop_recall = float(prop_detected / total_positives) if total_positives > 0 else 0.0
        prop_touched_rate = float(len(prop_selected) / n_val) if n_val > 0 else 0.0

        proposed_metrics = {
            "budget_multiple": prop_multiple,
            "touched_count": len(prop_selected),
            "touched_rate": round(prop_touched_rate, 4),
            "fraud_detected": prop_detected,
            "total_fraud": total_positives,
            "recall": round(prop_recall, 4),
        }

        # Check Workload Constraints
        workload_ok = prop_multiple <= self.max_workload_multiple
        # Acceptance condition: Proposed recall must not degrade by more than 1 pp compared to baseline
        recall_ok = prop_recall >= (base_recall - 0.01)

        rejection_reasons: list[str] = []
        if not workload_ok:
            rejection_reasons.append(
                f"Proposed budget multiple {prop_multiple} exceeds maximum limit {self.max_workload_multiple}"
            )
        if not recall_ok:
            rejection_reasons.append(
                f"Proposed recall {prop_recall:.4f} is inferior to baseline {base_recall:.4f}"
            )

        passed = workload_ok and recall_ok
        status: ProposalReplayStatus = "AWAITING_HUMAN_APPROVAL" if passed else "REJECTED"

        record_data = {
            "proposal_id": proposal.proposal_id,
            "base_cfg_hash": proposal.base_cfg_hash,
            "target_cfg_hash": target_cfg_hash,
            "status": status,
            "schema_valid": True,
            "hash_matched": True,
            "keys_valid": True,
            "validation_passed": passed,
            "workload_constraint_passed": workload_ok,
            "baseline_metrics": baseline_metrics,
            "proposed_metrics": proposed_metrics,
            "rejection_reasons": rejection_reasons,
            "approved_by": None,
            "approval_timestamp": None,
            "created_at": datetime.now(timezone.utc),
            "record_hash": ZERO_HASH,
        }
        rec_bytes = _canonical_json_bytes({k: v for k, v in record_data.items() if k != "record_hash"})
        record_data["record_hash"] = hashlib.sha256(rec_bytes).hexdigest()
        return ReplayEvaluationRecord.model_validate(record_data)

    def apply_human_approval(
        self,
        record: ReplayEvaluationRecord,
        approver_id: str,
        approver_role: str,
    ) -> ReplayEvaluationRecord:
        """Apply explicit human sign-off to activate an approved proposal.

        Enforces Human-in-the-Loop invariant: Cannot activate a proposal that was rejected
        or has not passed validation replay.
        """
        if record.status != "AWAITING_HUMAN_APPROVAL":
            raise ValueError(
                f"Cannot approve proposal with status '{record.status}'. "
                "Only proposals with status 'AWAITING_HUMAN_APPROVAL' may be signed off."
            )

        if not approver_id or not approver_role:
            raise ValueError("approver_id and approver_role are required for audit sign-off")

        approver_sig = f"{approver_role}:{approver_id}"
        now = datetime.now(timezone.utc)

        update_dict = {
            "status": "APPROVED_ACTIVE",
            "approved_by": approver_sig,
            "approval_timestamp": now,
        }
        updated = record.model_copy(update=update_dict)

        # Recompute audit record hash
        rec_dict = updated.model_dump(mode="json", exclude={"record_hash"})
        rec_hash = hashlib.sha256(_canonical_json_bytes(rec_dict)).hexdigest()
        return updated.model_copy(update={"record_hash": rec_hash})
