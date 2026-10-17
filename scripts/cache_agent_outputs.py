"""Run and cache permitted agent outputs for SignalGate Gate G6.

Applies the G3 AgentSupervisor, CaseCopilot, and ClaimVerifier to sanitized
audit records, caching verified outputs by input hash to results/agent_cache.json.

Security & Boundary Invariants:
1. Agent ingests strictly AgentCaseView records; zero raw features or labels.
2. Routine cases are deterministically skipped by the AgentSupervisor.
3. Escalated cases (FRAUD_ALERT, MANUAL_REVIEW, HELD) generate verified briefs.
4. Offline mock provider ensures reproducible, deterministic execution without network.
5. Cached records store verified claims, rendered statements, and SHA-256 provenance hashes.
"""

from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import numpy as np
import pandas as pd

from agents.claim_verifier import ClaimVerifier
from agents.copilot import CaseCopilot
from agents.supervisor import AgentSupervisor
from schemas.agent_view import AgentCaseView
from schemas.contracts import AuditRecord

RESULTS_DIR = ROOT / "results"
CACHE_FILE = RESULTS_DIR / "agent_cache.json"
RESULTS_FILE = RESULTS_DIR / "results.json"
SPLIT_MANIFEST_FILE = RESULTS_DIR / "split_manifest.json"


def generate_agent_cache(
    output_dir: Path | str | None = None,
    results_file: Path | str | None = None,
    n_sample: int = 50,
) -> dict:
    out_dir = Path(output_dir) if output_dir else RESULTS_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    cache_file = out_dir / "agent_cache.json"

    # 1. Load hashes from results.json
    res_path = Path(results_file) if results_file else (out_dir / "results.json" if (out_dir / "results.json").exists() else RESULTS_FILE)
    results_data = json.loads(res_path.read_text(encoding="utf-8"))
    cfg_hash = results_data["pre_eval_freeze_record"]["hashes"]["config_yaml_sha256"]
    split_hash = results_data["pre_eval_freeze_record"]["hashes"]["test_split_hash"]

    # 2. Initialize Agent Architecture
    verifier = ClaimVerifier()
    copilot = CaseCopilot(verifier=verifier)
    supervisor = AgentSupervisor(copilot=copilot)

    # 3. Create a diverse set of representative audit records covering all actions
    actions_scenarios = [
        ("FRAUD_ALERT", "R1_HIGH_RISK", 0.92, 0.08, 0.06),
        ("FRAUD_ALERT", "R1_HIGH_RISK", 0.86, 0.12, 0.09),
        ("MANUAL_REVIEW", "R2_INTERMEDIATE_RISK", 0.54, 0.15, 0.11),
        ("MANUAL_REVIEW", "R3_MODEL_DISAGREEMENT", 0.42, 0.28, 0.22),
        ("HELD", "R6_QUEUE_CAPACITY", 0.65, 0.10, 0.07),
        ("DEFERRED", "R6_QUEUE_CAPACITY", 0.48, 0.14, 0.10),
        ("ROUTINE", "R5_LOW_RISK_RELIABLE", 0.02, 0.01, 0.01),
        ("ROUTINE", "R5_LOW_RISK_RELIABLE", 0.05, 0.02, 0.01),
    ]

    cached_entries: list[dict] = []

    for idx, (action, reason, p_val, u_val, u2_val) in enumerate(actions_scenarios * 6):
        record_id = f"tx_cache_{300000 + idx}"
        audit_rec = AuditRecord(
            id=record_id,
            p=p_val,
            u=u_val,
            u2=u2_val,
            n=5.0,
            action=action,  # type: ignore[arg-type]
            reason=reason,  # type: ignore[arg-type]
            cfg_hash=cfg_hash,
            split_hash=split_hash,
            record_hash=f"{idx:064x}",
        )

        # Convert to strict allowlisted AgentCaseView
        case_view = AgentCaseView.from_audit_record(audit_rec)

        # Dispatch via Deterministic Supervisor
        is_eligible = supervisor.is_eligible(case_view)
        agent_record = supervisor.dispatch(case_view)

        if agent_record is not None:
            # Render statements from verified claims
            verified_claims, statements, _ = verifier.verify_all(agent_record.claims, case_view)
            entry = {
                "record_id": record_id,
                "agent_id": agent_record.agent_id,
                "provider": "offline_mock",
                "execution_mode": "deterministic_offline",
                "status": agent_record.status,
                "action": action,
                "reason": reason,
                "p": p_val,
                "u": u_val,
                "u2": u2_val,
                "n": 5.0,
                "input_hash": agent_record.input_hash,
                "output_hash": agent_record.output_hash,
                "cfg_hash": agent_record.cfg_hash,
                "split_hash": split_hash,
                "claims_count": len(verified_claims),
                "verified_claims": [c.model_dump(mode="json") for c in verified_claims],
                "verified_statements": statements,
                "timestamp": agent_record.timestamp.isoformat(),
            }
        else:
            entry = {
                "record_id": record_id,
                "agent_id": "none",
                "provider": "none",
                "execution_mode": "supervisor_skipped",
                "status": "ineligible_routine",
                "action": action,
                "reason": reason,
                "p": p_val,
                "u": u_val,
                "u2": u2_val,
                "n": 5.0,
                "input_hash": None,
                "output_hash": None,
                "cfg_hash": cfg_hash,
                "split_hash": split_hash,
                "claims_count": 0,
                "verified_claims": [],
                "verified_statements": ["ROUTINE auto-cleared case: ineligible for agent dispatch."],
                "timestamp": None,
            }
        cached_entries.append(entry)

    cache_payload = {
        "cache_version": "SignalGate-G6-AgentCache-v1.0",
        "description": "Pre-verified agent outputs and decision-support briefs for sample audit cases",
        "total_cached": len(cached_entries),
        "eligible_cases": sum(1 for e in cached_entries if e["status"] != "ineligible_routine"),
        "ineligible_routine_cases": sum(1 for e in cached_entries if e["status"] == "ineligible_routine"),
        "records": cached_entries,
    }

    cache_file.write_text(json.dumps(cache_payload, indent=2), encoding="utf-8")
    print(f"Generated {len(cached_entries)} cached agent records at {cache_file}")
    return cache_payload


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="SignalGate Gate G6 Agent Cache Generator")
    parser.add_argument("--output-dir", default=None, help="Directory to save agent_cache.json")
    parser.add_argument("--results-file", default=None, help="Path to results.json to read hashes from")
    args = parser.parse_args()
    generate_agent_cache(output_dir=args.output_dir, results_file=args.results_file)
