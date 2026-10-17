"""Deterministic Claim Ledger for SignalGate Gate G6.

Validates and verifies numerical performance claims against actual, immutable
evaluation artifacts (results/results.json, results/pre_eval_freeze_record.json).

Design & Governance Principles:
1. Ground Truth Provenance: Claims must cite their exact source artifact, metric name,
   scenario ID, sample size, and cryptographic configuration hash.
2. Evidence Type Classification: Strictly categorizes evidence into:
   - measured real data
   - measured synthetic data
   - assumption
   - planned work
   - unavailable evidence
   - inconclusive findings
3. Planted Error Detection: Deterministically rejects fabricated, altered, or unsupported
   numbers, producing explicit rejection reasons.
4. Zero Fabrication: Never invents missing metrics or silently repairs discrepancies.
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator

from schemas.contracts import SHA256_PATTERN

EvidenceClassification = Literal[
    "measured real data",
    "measured synthetic data",
    "assumption",
    "planned work",
    "unavailable evidence",
    "inconclusive findings",
]


class ReportableClaim(BaseModel):
    """A formal, typed numerical or statistical claim citing provenance."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    claim_id: str = Field(min_length=1)
    metric_name: str = Field(min_length=1)
    scenario_id: str = Field(min_length=1)
    claimed_value: float | int | str | bool
    evidence_type: EvidenceClassification
    source_artifact: str = Field(min_length=1)
    sample_size: int | None = Field(default=None, ge=0)
    config_hash: str | None = Field(default=None, pattern=SHA256_PATTERN)
    description: str = Field(min_length=1)


class LedgerVerificationResult(BaseModel):
    """Outcome of verifying a ReportableClaim against immutable evidence artifacts."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    claim_id: str = Field(min_length=1)
    is_verified: bool
    claimed_value: Any
    actual_value: Any | None = None
    rejection_reason: str | None = None
    source_artifact_path: str
    verified_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @field_validator("verified_at")
    @classmethod
    def timestamp_must_include_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("verified_at must include a timezone")
        return value


class ClaimLedger:
    """Audit engine validating reported performance claims against saved evidence artifacts."""

    def __init__(
        self,
        results_path: Path | str = "results/results.json",
        freeze_record_path: Path | str = "results/pre_eval_freeze_record.json",
    ) -> None:
        self.results_path = Path(results_path)
        self.freeze_record_path = Path(freeze_record_path)

        self._results_data: dict[str, Any] | None = None
        self._freeze_data: dict[str, Any] | None = None

        if self.results_path.exists():
            try:
                self._results_data = json.loads(self.results_path.read_text(encoding="utf-8"))
            except Exception:
                self._results_data = None

        if self.freeze_record_path.exists():
            try:
                self._freeze_data = json.loads(self.freeze_record_path.read_text(encoding="utf-8"))
            except Exception:
                self._freeze_data = None

    def verify_claim(self, claim: ReportableClaim) -> LedgerVerificationResult:
        """Verify a single claim against the saved result artifacts."""
        if not isinstance(claim, ReportableClaim):
            raise TypeError("verify_claim requires a ReportableClaim instance")

        # 1. Check artifact existence
        artifact_path = Path(claim.source_artifact)
        if not artifact_path.exists():
            return LedgerVerificationResult(
                claim_id=claim.claim_id,
                is_verified=False,
                claimed_value=claim.claimed_value,
                actual_value=None,
                rejection_reason=f"Source artifact not found: '{claim.source_artifact}'",
                source_artifact_path=str(artifact_path),
            )

        # Load artifact data if different from preloaded results_data
        eval_data = self._results_data
        if artifact_path.resolve() != self.results_path.resolve():
            try:
                eval_data = json.loads(artifact_path.read_text(encoding="utf-8"))
            except Exception as e:
                return LedgerVerificationResult(
                    claim_id=claim.claim_id,
                    is_verified=False,
                    claimed_value=claim.claimed_value,
                    actual_value=None,
                    rejection_reason=f"Failed to parse source artifact '{claim.source_artifact}': {e}",
                    source_artifact_path=str(artifact_path),
                )

        if eval_data is None:
            return LedgerVerificationResult(
                claim_id=claim.claim_id,
                is_verified=False,
                claimed_value=claim.claimed_value,
                actual_value=None,
                rejection_reason=f"Results artifact '{self.results_path}' is missing or unparseable",
                source_artifact_path=str(artifact_path),
            )

        # 2. Extract actual value based on scenario and metric name
        actual_val, actual_n = self._extract_metric_value(claim.scenario_id, claim.metric_name, data=eval_data)
        if actual_val is None:
            return LedgerVerificationResult(
                claim_id=claim.claim_id,
                is_verified=False,
                claimed_value=claim.claimed_value,
                actual_value=None,
                rejection_reason=(
                    f"Metric '{claim.metric_name}' not found for scenario '{claim.scenario_id}' "
                    f"in '{claim.source_artifact}'"
                ),
                source_artifact_path=str(artifact_path),
            )

        # 3. Check sample size provenance if specified
        if claim.sample_size is not None and actual_n is not None:
            if claim.sample_size != actual_n:
                return LedgerVerificationResult(
                    claim_id=claim.claim_id,
                    is_verified=False,
                    claimed_value=claim.claimed_value,
                    actual_value=actual_val,
                    rejection_reason=(
                        f"Sample size mismatch: claim states n={claim.sample_size}, "
                        f"artifact records n={actual_n}"
                    ),
                    source_artifact_path=str(artifact_path),
                )

        # 4. Check configuration hash provenance if specified
        if claim.config_hash is not None and self._freeze_data is not None:
            frozen_cfg = self._freeze_data.get("hashes", {}).get("config_yaml_sha256")
            if claim.config_hash != frozen_cfg:
                return LedgerVerificationResult(
                    claim_id=claim.claim_id,
                    is_verified=False,
                    claimed_value=claim.claimed_value,
                    actual_value=actual_val,
                    rejection_reason=(
                        f"Config hash mismatch: claim references '{claim.config_hash}', "
                        f"freeze record specifies '{frozen_cfg}'"
                    ),
                    source_artifact_path=str(artifact_path),
                )

        # 5. Numerical / Value Equality Check
        matches = self._compare_values(claim.claimed_value, actual_val)
        if not matches:
            return LedgerVerificationResult(
                claim_id=claim.claim_id,
                is_verified=False,
                claimed_value=claim.claimed_value,
                actual_value=actual_val,
                rejection_reason=(
                    f"Planted or incorrect value: claim asserts {claim.claimed_value!r}, "
                    f"verified artifact records {actual_val!r}"
                ),
                source_artifact_path=str(artifact_path),
            )

        return LedgerVerificationResult(
            claim_id=claim.claim_id,
            is_verified=True,
            claimed_value=claim.claimed_value,
            actual_value=actual_val,
            rejection_reason=None,
            source_artifact_path=str(artifact_path),
        )

    def verify_all(
        self,
        claims: list[ReportableClaim],
    ) -> tuple[list[LedgerVerificationResult], int, int]:
        """Verify multiple claims, returning results, verified count, and rejected count."""
        results = [self.verify_claim(c) for c in claims]
        verified_cnt = sum(1 for r in results if r.is_verified)
        rejected_cnt = len(results) - verified_cnt
        return results, verified_cnt, rejected_cnt

    def _extract_metric_value(
        self,
        scenario_id: str,
        metric_name: str,
        data: dict[str, Any] | None = None,
    ) -> tuple[Any | None, int | None]:
        """Navigate results.json hierarchy to extract the ground-truth value."""
        target_data = data if data is not None else self._results_data
        if target_data is None:
            return None, None

        scenarios = target_data.get("scenarios", {})

        # Scenario-specific metrics
        if scenario_id in scenarios:
            s_dict = scenarios[scenario_id]
            sample_size = s_dict.get("sample_size")

            if metric_name == "sample_size":
                return sample_size, sample_size

            # Look in paired_bootstrap
            bs = s_dict.get("paired_bootstrap", {})
            if metric_name in bs:
                return bs[metric_name], sample_size

            # Look in candidate_p5
            p5 = s_dict.get("candidate_p5", {})
            if metric_name in p5:
                return p5[metric_name], sample_size

            # Look in baseline_b2
            b2 = s_dict.get("baseline_b2", {})
            if metric_name.startswith("b2_"):
                b2_key = metric_name[3:]
                if b2_key in b2:
                    return b2[b2_key], sample_size
            elif metric_name in b2:
                return b2[metric_name], sample_size

        # Acceptance Criteria
        ac_dict = target_data.get("acceptance_criteria", {})
        if scenario_id == "acceptance" and metric_name in ac_dict:
            return ac_dict[metric_name].get("status"), None

        # Latency Benchmark
        latency_dict = target_data.get("latency_benchmark", {})
        if scenario_id == "latency" and metric_name in latency_dict:
            return latency_dict[metric_name], latency_dict.get("single_row_iterations")

        return None, None

    def build_standard_claims(self) -> list[ReportableClaim]:
        """Construct formal ReportableClaims for all headline evaluation metrics."""
        cfg_hash = None
        if self._freeze_data is not None:
            cfg_hash = self._freeze_data.get("hashes", {}).get("config_yaml_sha256")

        claims = [
            # S0: Chronological Test Set (Measured Real Data)
            ReportableClaim(
                claim_id="CLM_S0_N",
                metric_name="sample_size",
                scenario_id="S0",
                claimed_value=118108,
                evidence_type="measured real data",
                source_artifact=str(self.results_path),
                sample_size=118108,
                config_hash=cfg_hash,
                description="S0 Chronological Test Set sample size",
            ),
            ReportableClaim(
                claim_id="CLM_S0_RECALL_P5",
                metric_name="recall",
                scenario_id="S0",
                claimed_value=0.513287,
                evidence_type="measured real data",
                source_artifact=str(self.results_path),
                sample_size=118108,
                config_hash=cfg_hash,
                description="S0 SignalGate P5 candidate recall at 1.5x review budget",
            ),
            ReportableClaim(
                claim_id="CLM_S0_RECALL_B2",
                metric_name="b2_recall",
                scenario_id="S0",
                claimed_value=0.505167,
                evidence_type="measured real data",
                source_artifact=str(self.results_path),
                sample_size=118108,
                config_hash=cfg_hash,
                description="S0 Baseline B2 recall at 1.5x review budget",
            ),
            ReportableClaim(
                claim_id="CLM_S0_DELTA_RECALL",
                metric_name="delta_point_estimate",
                scenario_id="S0",
                claimed_value=0.00812,
                evidence_type="measured real data",
                source_artifact=str(self.results_path),
                sample_size=118108,
                config_hash=cfg_hash,
                description="S0 Paired difference in recall (P5 - B2)",
            ),
            ReportableClaim(
                claim_id="CLM_S0_CI_LOWER",
                metric_name="ci_lower",
                scenario_id="S0",
                claimed_value=0.000749,
                evidence_type="measured real data",
                source_artifact=str(self.results_path),
                sample_size=118108,
                config_hash=cfg_hash,
                description="S0 95% Bootstrap CI lower bound for delta recall",
            ),
            ReportableClaim(
                claim_id="CLM_S0_CI_UPPER",
                metric_name="ci_upper",
                scenario_id="S0",
                claimed_value=0.014092,
                evidence_type="measured real data",
                source_artifact=str(self.results_path),
                sample_size=118108,
                config_hash=cfg_hash,
                description="S0 95% Bootstrap CI upper bound for delta recall",
            ),
            # S1: Late-Period Test Scenario (Measured Real Data)
            ReportableClaim(
                claim_id="CLM_S1_N",
                metric_name="sample_size",
                scenario_id="S1",
                claimed_value=31582,
                evidence_type="measured real data",
                source_artifact=str(self.results_path),
                sample_size=31582,
                config_hash=cfg_hash,
                description="S1 Late-Period Test Scenario sample size",
            ),
            ReportableClaim(
                claim_id="CLM_S1_DELTA_RECALL",
                metric_name="delta_point_estimate",
                scenario_id="S1",
                claimed_value=0.02475,
                evidence_type="measured real data",
                source_artifact=str(self.results_path),
                sample_size=31582,
                config_hash=cfg_hash,
                description="S1 Late-Period Paired delta recall (+2.48 pp)",
            ),
            # S2: Constructed Real-Data Shift (Validation Window Slice)
            ReportableClaim(
                claim_id="CLM_S2_N",
                metric_name="sample_size",
                scenario_id="S2",
                claimed_value=27390,
                evidence_type="measured real data",
                source_artifact=str(self.results_path),
                sample_size=27390,
                config_hash=cfg_hash,
                description="S2 Real-Data Shift authoritative sample size",
            ),
            ReportableClaim(
                claim_id="CLM_S2_DELTA_RECALL",
                metric_name="delta_point_estimate",
                scenario_id="S2",
                claimed_value=0.02369,
                evidence_type="measured real data",
                source_artifact=str(self.results_path),
                sample_size=27390,
                config_hash=cfg_hash,
                description="S2 Real-Data Shift Paired delta recall (+2.37 pp)",
            ),
            # S3: Synthetic Perturbation Scenario (Measured Synthetic Data)
            ReportableClaim(
                claim_id="CLM_S3_N",
                metric_name="sample_size",
                scenario_id="S3",
                claimed_value=59054,
                evidence_type="measured synthetic data",
                source_artifact=str(self.results_path),
                sample_size=59054,
                config_hash=cfg_hash,
                description="S3 Synthetic Perturbation sample size",
            ),
            ReportableClaim(
                claim_id="CLM_S3_DELTA_RECALL",
                metric_name="delta_point_estimate",
                scenario_id="S3",
                claimed_value=0.05002,
                evidence_type="measured synthetic data",
                source_artifact=str(self.results_path),
                sample_size=59054,
                config_hash=cfg_hash,
                description="S3 Synthetic Perturbation Paired delta recall (+5.00 pp)",
            ),
            # Latency (Measured Real Data on AMD64 Host)
            ReportableClaim(
                claim_id="CLM_LATENCY_P95",
                metric_name="single_row_p95_ms",
                scenario_id="latency",
                claimed_value=8.342,
                evidence_type="measured real data",
                source_artifact=str(self.results_path),
                sample_size=100,
                config_hash=cfg_hash,
                description="Single-row p95 latency benchmark (AMD64 host)",
            ),
            # Acceptance Criteria (Measured Real Data)
            ReportableClaim(
                claim_id="CLM_AC1_STATUS",
                metric_name="AC1",
                scenario_id="acceptance",
                claimed_value="FAIL",
                evidence_type="measured real data",
                source_artifact=str(self.results_path),
                sample_size=None,
                config_hash=cfg_hash,
                description="AC1 Status (+0.81 pp < +2.0 pp threshold -> FAIL)",
            ),
            ReportableClaim(
                claim_id="CLM_AC3_STATUS",
                metric_name="AC3",
                scenario_id="acceptance",
                claimed_value="PASS",
                evidence_type="measured real data",
                source_artifact=str(self.results_path),
                sample_size=None,
                config_hash=cfg_hash,
                description="AC3 Status (P5 outperforms B2 across S0-S3 -> PASS)",
            ),
            ReportableClaim(
                claim_id="CLM_AC5_STATUS",
                metric_name="AC5",
                scenario_id="acceptance",
                claimed_value="PASS",
                evidence_type="measured real data",
                source_artifact=str(self.results_path),
                sample_size=None,
                config_hash=cfg_hash,
                description="AC5 Status (p95 latency 8.34ms <= 50ms -> PASS)",
            ),
        ]
        return claims

    @staticmethod
    def _compare_values(claimed: Any, actual: Any, tol: float = 1e-4) -> bool:
        """Deterministic comparison with safe float tolerance."""
        if isinstance(claimed, (int, float)) and isinstance(actual, (int, float)):
            return abs(float(claimed) - float(actual)) <= tol
        return str(claimed).strip().lower() == str(actual).strip().lower()
