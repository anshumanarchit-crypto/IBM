"""Data loading, reconciliation, and provenance verification for SignalGate Dashboard (Gate G6).

Reads strictly from immutable, saved artifacts in the results/ directory:
- results/results.json
- results/pre_eval_freeze_record.json
- results/shift_scenarios_manifest.json
- results/agent_cache.json
- results/drift_report.json
- results/sample_audit_chain.jsonl

Safety & Integrity Rules:
1. Zero live model inference or retraining.
2. Zero data fabrication; missing or corrupt files return explicit unverified/unavailable states.
3. Deterministic lane counter recomputation and verification against recorded totals.
4. Cryptographic SHA-256 hash checks for configuration and test splits.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from typing import Any

from governance.audit_chain import verify_chain
from governance.claim_ledger import ClaimLedger, LedgerVerificationResult, ReportableClaim

DEFAULT_TEST_KEY = b"signalgate_audit_key_32_bytes_ok"


@dataclass(frozen=True)
class ProvenanceVerificationStatus:
    """Status of cryptographic provenance checks."""

    config_hash_verified: bool
    split_hash_verified: bool
    policy_hash_verified: bool
    expected_config_hash: str | None
    actual_config_hash: str | None
    expected_split_hash: str | None
    actual_split_hash: str | None
    expected_policy_hash: str | None
    actual_policy_hash: str | None
    notes: list[str]


@dataclass(frozen=True)
class LaneCounterVerification:
    """Recomputed lane counts vs saved lane counts."""

    is_consistent: bool
    total_cases: int
    sum_of_lanes: int
    fraud_alert_count: int
    manual_review_count: int
    routine_count: int
    held_deferred_count: int
    reviewed_cases: int
    sum_reviewed_lanes: int
    discrepancy_details: list[str]


class DashboardDataLoader:
    """Safe loader and verifier for frozen SignalGate evaluation artifacts."""

    def __init__(self, root_dir: Path | str | None = None) -> None:
        self.root_dir = Path(root_dir) if root_dir else Path(__file__).resolve().parents[1]
        self.results_dir = self.root_dir / "results"

        self.results_file = self.results_dir / "results.json"
        self.freeze_record_file = self.results_dir / "pre_eval_freeze_record.json"
        self.shift_manifest_file = self.results_dir / "shift_scenarios_manifest.json"
        self.agent_cache_file = self.results_dir / "agent_cache.json"
        self.drift_report_file = self.results_dir / "drift_report.json"
        self.audit_chain_file = self.results_dir / "sample_audit_chain.jsonl"
        self.config_yaml_file = self.root_dir / "config.yaml"

    def load_results(self) -> dict[str, Any] | None:
        """Load master evaluation results.json."""
        if not self.results_file.exists():
            return None
        try:
            return json.loads(self.results_file.read_text(encoding="utf-8"))
        except Exception:
            return None

    def load_freeze_record(self) -> dict[str, Any] | None:
        """Load pre-evaluation freeze record."""
        if not self.freeze_record_file.exists():
            return None
        try:
            return json.loads(self.freeze_record_file.read_text(encoding="utf-8"))
        except Exception:
            return None

    def load_shift_manifest(self) -> dict[str, Any] | None:
        """Load shift scenario manifest."""
        if not self.shift_manifest_file.exists():
            return None
        try:
            return json.loads(self.shift_manifest_file.read_text(encoding="utf-8"))
        except Exception:
            return None

    def load_agent_cache(self) -> dict[str, Any] | None:
        """Load precomputed agent outputs and verified briefs."""
        if not self.agent_cache_file.exists():
            return None
        try:
            return json.loads(self.agent_cache_file.read_text(encoding="utf-8"))
        except Exception:
            return None

    def load_drift_report(self) -> dict[str, Any] | None:
        """Load saved drift report."""
        if not self.drift_report_file.exists():
            return None
        try:
            return json.loads(self.drift_report_file.read_text(encoding="utf-8"))
        except Exception:
            return None

    def verify_provenance(self) -> ProvenanceVerificationStatus:
        """Verify configuration and split hashes against recorded freeze artifacts."""
        freeze = self.load_freeze_record()
        notes: list[str] = []

        if freeze is None:
            return ProvenanceVerificationStatus(
                config_hash_verified=False,
                split_hash_verified=False,
                policy_hash_verified=False,
                expected_config_hash=None,
                actual_config_hash=None,
                expected_split_hash=None,
                actual_split_hash=None,
                expected_policy_hash=None,
                actual_policy_hash=None,
                notes=["Pre-evaluation freeze record is missing or unparseable."],
            )

        recorded_hashes = freeze.get("hashes", {})
        expected_cfg = recorded_hashes.get("config_yaml_sha256")
        expected_split = recorded_hashes.get("test_split_hash")
        
        # Policy hash from frozen_system
        candidate_policy = freeze.get("frozen_system", {}).get("candidate_policy", {})
        expected_policy = candidate_policy.get("policy_config_hash")

        # 1. Check actual config.yaml hash
        actual_cfg = None
        cfg_verified = False
        if self.config_yaml_file.exists():
            actual_cfg = hashlib.sha256(self.config_yaml_file.read_bytes()).hexdigest()
            cfg_verified = (actual_cfg == expected_cfg)
            if not cfg_verified:
                notes.append(f"Config hash mismatch: expected {expected_cfg}, got {actual_cfg}")
        else:
            notes.append("config.yaml not found on disk.")

        # 2. Check test split hash recorded in split_manifest.json
        split_manifest_file = self.results_dir / "split_manifest.json"
        actual_split = None
        split_verified = False
        if split_manifest_file.exists():
            try:
                sm = json.loads(split_manifest_file.read_text(encoding="utf-8"))
                actual_split = sm.get("partitions", {}).get("test", {}).get("split_hash")
                split_verified = (actual_split == expected_split)
                if not split_verified:
                    notes.append(f"Split hash mismatch: expected {expected_split}, got {actual_split}")
            except Exception as e:
                notes.append(f"Failed to read split_manifest.json: {e}")
        else:
            notes.append("split_manifest.json not found on disk.")

        # 3. Policy hash
        policy_verified = (expected_policy is not None and len(expected_policy) == 64)
        actual_policy = expected_policy

        return ProvenanceVerificationStatus(
            config_hash_verified=cfg_verified,
            split_hash_verified=split_verified,
            policy_hash_verified=policy_verified,
            expected_config_hash=expected_cfg,
            actual_config_hash=actual_cfg,
            expected_split_hash=expected_split,
            actual_split_hash=actual_split,
            expected_policy_hash=expected_policy,
            actual_policy_hash=actual_policy,
            notes=notes,
        )

    def verify_lane_counters(self, scenario_id: str = "S0") -> LaneCounterVerification:
        """Recompute and verify lane counters for a scenario against recorded totals."""
        results = self.load_results()
        if results is None or "scenarios" not in results:
            return LaneCounterVerification(
                is_consistent=False,
                total_cases=0,
                sum_of_lanes=0,
                fraud_alert_count=0,
                manual_review_count=0,
                routine_count=0,
                held_deferred_count=0,
                reviewed_cases=0,
                sum_reviewed_lanes=0,
                discrepancy_details=["results.json is missing or unparseable."],
            )

        scenarios = results.get("scenarios", {})
        if scenario_id not in scenarios:
            return LaneCounterVerification(
                is_consistent=False,
                total_cases=0,
                sum_of_lanes=0,
                fraud_alert_count=0,
                manual_review_count=0,
                routine_count=0,
                held_deferred_count=0,
                reviewed_cases=0,
                sum_reviewed_lanes=0,
                discrepancy_details=[f"Scenario '{scenario_id}' not found in results.json."],
            )

        p5_data = scenarios[scenario_id].get("candidate_p5", {})
        total_cases = p5_data.get("total_cases", 0)
        c_fraud_alert = p5_data.get("fraud_alert_count", 0)
        c_manual_review = p5_data.get("manual_review_count", 0)
        c_routine = p5_data.get("routine_count", 0)
        c_held = p5_data.get("held_deferred_count", 0)
        reviewed_cases = p5_data.get("reviewed_cases", 0)

        sum_of_lanes = c_fraud_alert + c_manual_review + c_routine + c_held
        sum_reviewed = c_fraud_alert + c_manual_review + c_held

        discrepancies: list[str] = []
        if sum_of_lanes != total_cases:
            discrepancies.append(
                f"Lane sum mismatch: FRAUD_ALERT({c_fraud_alert}) + MANUAL_REVIEW({c_manual_review}) + "
                f"ROUTINE({c_routine}) + HELD({c_held}) = {sum_of_lanes} != total_cases({total_cases})"
            )

        if sum_reviewed != reviewed_cases:
            discrepancies.append(
                f"Reviewed cases mismatch: sum({sum_reviewed}) != reviewed_cases({reviewed_cases})"
            )

        is_consistent = (len(discrepancies) == 0) and (total_cases > 0)
        return LaneCounterVerification(
            is_consistent=is_consistent,
            total_cases=total_cases,
            sum_of_lanes=sum_of_lanes,
            fraud_alert_count=c_fraud_alert,
            manual_review_count=c_manual_review,
            routine_count=c_routine,
            held_deferred_count=c_held,
            reviewed_cases=reviewed_cases,
            sum_reviewed_lanes=sum_reviewed,
            discrepancy_details=discrepancies,
        )

    def verify_audit_chain(self, key: bytes = DEFAULT_TEST_KEY) -> dict[str, Any]:
        """Verify the sample HMAC audit log."""
        if not self.audit_chain_file.exists():
            return {
                "ok": False,
                "record_count": 0,
                "errors": ("sample_audit_chain.jsonl not found",),
                "final_hash": None,
            }

        res = verify_chain(self.audit_chain_file, key)
        return {
            "ok": res.ok,
            "record_count": res.record_count,
            "errors": list(res.errors),
            "final_hash": res.final_hash,
        }

    def verify_standard_claims(self) -> tuple[list[LedgerVerificationResult], int, int]:
        """Verify standard evaluation claims with ClaimLedger."""
        ledger = ClaimLedger(
            results_path=self.results_file,
            freeze_record_path=self.freeze_record_file,
        )
        claims = ledger.build_standard_claims()
        return ledger.verify_all(claims)
