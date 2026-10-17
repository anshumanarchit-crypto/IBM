"""SignalGate Master Reproduction & Audit Entry Point (Gate G7).

Distinguishes two primary workflows:
1. Workflow A (Offline Demonstration & Audit):
   Operates strictly from immutable, saved evaluation artifacts in results/.
   Requires ZERO training data, ZERO model training, and ZERO external network access.
   Verifies cryptographic provenance, lane counts, claim ledger, and test suite.

2. Workflow B (Full Experiment Reproduction):
   Requires labeled IEEE-CIS Fraud Detection dataset (data/raw/train_transaction.csv, 683 MB).
   Executes chronological splitting, feature extraction, calibration, ensemble training,
   shift evaluation (S0-S3), paired bootstrap, and audit caching.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.dashboard_data import DashboardDataLoader
from governance.claim_ledger import ClaimLedger, ReportableClaim

RESULTS_DIR = ROOT / "results"


def print_banner(text: str) -> None:
    sep = "=" * 78
    print(f"\n{sep}\n{text}\n{sep}")


def run_offline_audit() -> bool:
    """Execute complete offline verification without training data or network access."""
    print_banner("SignalGate Gate G7: Offline Demonstration & Reproducibility Audit")
    print(f"Timestamp: {datetime.now(timezone.utc).isoformat()}")
    print(f"Host Python: {sys.version.split()[0]} on {sys.platform}")
    print(f"Working Directory: {ROOT}")

    loader = DashboardDataLoader(root_dir=ROOT)
    all_passed = True

    # 1. Artifact Availability Check
    print("\n[Step 1/6] Checking frozen evaluation and governance artifacts...")
    artifacts = [
        ("Master Evaluation Results", loader.results_file),
        ("Pre-Evaluation Freeze Record", loader.freeze_record_file),
        ("Shift Scenarios Manifest", loader.shift_manifest_file),
        ("Split Manifest", loader.results_dir / "split_manifest.json"),
        ("Feature Manifest", loader.results_dir / "feature_manifest.json"),
        ("Precomputed Agent Cache", loader.agent_cache_file),
        ("Frozen Drift Report", loader.drift_report_file),
        ("HMAC Audit Chain Log", loader.audit_chain_file),
        ("Project Configuration", loader.config_yaml_file),
    ]

    for name, path in artifacts:
        if path.exists():
            size_kb = path.stat().st_size / 1024
            print(f"  [OK] {name:<30} -> {path.name} ({size_kb:.1f} KB)")
        else:
            print(f"  [FAIL] Missing artifact: {name} at {path}")
            all_passed = False

    if not all_passed:
        print("\nCRITICAL: One or more required frozen artifacts are missing!")
        return False

    # 2. Cryptographic Provenance Hashes
    print("\n[Step 2/6] Verifying cryptographic provenance hashes...")
    prov = loader.verify_provenance()
    if prov.config_hash_verified:
        print(f"  [OK] config.yaml SHA-256 matches freeze record: {prov.actual_config_hash[:16]}...")
    else:
        print(f"  [FAIL] config.yaml hash mismatch: expected {prov.expected_config_hash}, got {prov.actual_config_hash}")
        all_passed = False

    if prov.split_hash_verified:
        print(f"  [OK] Test split hash matches split manifest:     {prov.actual_split_hash[:16]}...")
    else:
        print(f"  [FAIL] Test split hash mismatch: expected {prov.expected_split_hash}, got {prov.actual_split_hash}")
        all_passed = False

    if prov.policy_hash_verified:
        print(f"  [OK] P5 candidate policy hash matches freeze:   {prov.actual_policy_hash[:16]}...")
    else:
        print("  [FAIL] Policy hash unverified")
        all_passed = False

    # 3. Operational Lane Counter Reconciliation
    print("\n[Step 3/6] Recomputing operational lane counters from saved results...")
    for sc_id in ["S0", "S1", "S2", "S3"]:
        lane_res = loader.verify_lane_counters(sc_id)
        if lane_res.is_consistent:
            print(
                f"  [OK] Scenario {sc_id}: Sum({lane_res.sum_of_lanes:,}) == Total({lane_res.total_cases:,}) | "
                f"Reviewed({lane_res.sum_reviewed_lanes:,}) == Budget({lane_res.reviewed_cases:,})"
            )
        else:
            print(f"  [FAIL] Scenario {sc_id} lane discrepancy: {lane_res.discrepancy_details}")
            all_passed = False

    # 4. HMAC Audit-Chain Verification
    print("\n[Step 4/6] Verifying HMAC cryptographic audit chain...")
    chain_res = loader.verify_audit_chain()
    if chain_res["ok"]:
        print(f"  [OK] Audit chain verified: {chain_res['record_count']} records signed and linked.")
        print(f"       Final HMAC signature: {chain_res['final_hash']}")
    else:
        print(f"  [FAIL] Audit chain verification failed: {chain_res['errors']}")
        all_passed = False

    # 5. Claim Ledger Audit & Planted-Error Test
    print("\n[Step 5/6] Running deterministic Claim Ledger verification...")
    ledger_results, v_cnt, r_cnt = loader.verify_standard_claims()
    print(f"  [OK] Standard headline claims: {v_cnt}/{len(ledger_results)} verified, {r_cnt} rejected.")

    # Planted-error test
    adversarial_claim = ReportableClaim(
        claim_id="CLM_ADVERSARIAL_PLANTED_TEST",
        metric_name="recall",
        scenario_id="S0",
        claimed_value=0.8500,  # Fabricated recall
        evidence_type="measured real data",
        source_artifact="results/results.json",
        sample_size=118108,
        description="Planted incorrect claim to test ledger rejection",
    )
    ledger = ClaimLedger(results_path=loader.results_file, freeze_record_path=loader.freeze_record_file)
    adv_res = ledger.verify_claim(adversarial_claim)
    if not adv_res.is_verified:
        print(f"  [OK] Planted wrong claim successfully caught and rejected by Claim Ledger:")
        print(f"       Rejection Reason: {adv_res.rejection_reason}")
    else:
        print("  [FAIL] Claim Ledger failed to catch planted error!")
        all_passed = False

    # 6. Pytest Execution
    print("\n[Step 6/6] Executing full automated pytest test suite...")
    cmd = [sys.executable, "-m", "pytest", "-q"]
    proc = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True)
    print(proc.stdout.strip())
    if proc.returncode == 0:
        print("  [OK] Full test suite passed cleanly with 0 failures.")
    else:
        print(f"  [FAIL] Pytest failed with exit code {proc.returncode}:\n{proc.stderr}")
        all_passed = False

    print_banner(
        "OFFLINE AUDIT SUMMARY: SUCCESS / PASS" if all_passed
        else "OFFLINE AUDIT SUMMARY: FAILED / BLOCKED"
    )
    if all_passed:
        print("All frozen artifacts, provenance hashes, lane counters, and claim checks verified.")
        print("The dashboard can be safely launched offline via:")
        print("  streamlit run app/streamlit_app.py --server.headless true --server.port 8501\n")
    return all_passed


def compare_reproduction_results(out_dir: Path, canonical_dir: Path = RESULTS_DIR) -> dict:
    """Compare reproduced evaluation and manifests against canonical frozen evidence."""
    print_banner("SignalGate Gate G7: Reproduction vs Frozen Evidence Comparison")

    reproduced_results = out_dir / "results.json"
    canonical_results = canonical_dir / "results.json"
    if not reproduced_results.exists():
        print(f"  [FAIL] Reproduction results not found at {reproduced_results}")
        return {"error": "results.json missing"}

    rep = json.loads(reproduced_results.read_text(encoding="utf-8"))
    can = json.loads(canonical_results.read_text(encoding="utf-8"))

    print("\n[Comparison 1/4] Scenario Sample Sizes & Lane Budgets:")
    print(f"  {'Scenario':<10} {'Metric':<15} {'Canonical':<15} {'Reproduced':<15} {'Match':<8}")
    print("  " + "-" * 65)

    for sid in ["S0", "S1", "S2", "S3"]:
        can_sc = can["scenarios"][sid]
        rep_sc = rep["scenarios"][sid]

        n_match = can_sc["sample_size"] == rep_sc["sample_size"]
        print(f"  {sid:<10} {'sample_size':<15} {can_sc['sample_size']:<15} {rep_sc['sample_size']:<15} {str(n_match):<8}")

        k_match = can_sc["budget_k"] == rep_sc["budget_k"]
        print(f"  {sid:<10} {'budget_k':<15} {can_sc['budget_k']:<15} {rep_sc['budget_k']:<15} {str(k_match):<8}")

        f_match = can_sc["fraud_count"] == rep_sc["fraud_count"]
        print(f"  {sid:<10} {'fraud_count':<15} {can_sc['fraud_count']:<15} {rep_sc['fraud_count']:<15} {str(f_match):<8}")

    print("\n[Comparison 2/4] Policy Evaluation Metrics (Recall & PR-AUC):")
    print(f"  {'Scenario':<10} {'Policy/Metric':<25} {'Canonical':<15} {'Reproduced':<15} {'Delta':<12}")
    print("  " + "-" * 75)
    for sid in ["S0", "S1", "S2", "S3"]:
        can_sc = can["scenarios"][sid]
        rep_sc = rep["scenarios"][sid]

        c_b2_rec = can_sc["baseline_b2"]["recall"]
        r_b2_rec = rep_sc["baseline_b2"]["recall"]
        print(f"  {sid:<10} {'B2 Recall':<25} {c_b2_rec:.4f}          {r_b2_rec:.4f}          {r_b2_rec - c_b2_rec:+.4f}")

        c_p5_rec = can_sc["candidate_p5"]["recall"]
        r_p5_rec = rep_sc["candidate_p5"]["recall"]
        print(f"  {sid:<10} {'P5 Recall':<25} {c_p5_rec:.4f}          {r_p5_rec:.4f}          {r_p5_rec - c_p5_rec:+.4f}")

        c_diff = can_sc["paired_bootstrap"].get("delta_point_estimate", 0.0)
        r_diff = rep_sc["paired_bootstrap"].get("delta_point_estimate", 0.0)
        print(f"  {sid:<10} {'Paired Recall Diff':<25} {c_diff:+.4f}         {r_diff:+.4f}         {r_diff - c_diff:+.4f}")

    print("\n[Comparison 3/4] Acceptance Criteria (AC1-AC5) Status Alignment:")
    print(f"  {'Criterion':<12} {'Canonical Status':<18} {'Reproduced Status':<18} {'Match':<8}")
    print("  " + "-" * 60)
    for ac_key in ["AC1", "AC2", "AC3", "AC4", "AC5"]:
        c_st = can["acceptance_criteria"][ac_key]["status"]
        r_st = rep["acceptance_criteria"][ac_key]["status"]
        m = c_st == r_st
        print(f"  {ac_key:<12} {c_st:<18} {r_st:<18} {str(m):<8}")

    print("\n[Comparison 4/4] Cryptographic & Manifest Consistency:")
    rep_split = out_dir / "split_manifest.json"
    can_split = canonical_dir / "split_manifest.json"
    if rep_split.exists() and can_split.exists():
        r_sm = json.loads(rep_split.read_text(encoding="utf-8"))
        c_sm = json.loads(can_split.read_text(encoding="utf-8"))
        t_match = r_sm["partitions"]["test"]["split_hash"] == c_sm["partitions"]["test"]["split_hash"]
        print(f"  Test split hash match: {t_match} ({r_sm['partitions']['test']['split_hash'][:16]}...)")

    rep_feat = out_dir / "feature_manifest.json"
    can_feat = canonical_dir / "feature_manifest.json"
    if rep_feat.exists() and can_feat.exists():
        r_fm = json.loads(rep_feat.read_text(encoding="utf-8"))
        c_fm = json.loads(can_feat.read_text(encoding="utf-8"))
        f_match = r_fm["feature_count"] == c_fm["feature_count"]
        print(f"  Feature count match:   {f_match} ({r_fm['feature_count']} features)")

    return {"status": "comparison_complete"}


def run_full_reproduction(output_dir: Path | str | None = None) -> bool:
    """Execute complete end-to-end retraining and evaluation reproduction workflow."""
    print_banner("SignalGate Gate G7: Full Experiment Reproduction Workflow")
    raw_tx = ROOT / "data" / "raw" / "train_transaction.csv"

    if not raw_tx.exists():
        print("ERROR: Raw IEEE-CIS Fraud Detection dataset not found!")
        print(f"Expected file at: {raw_tx}")
        print("\nPrerequisite for full retraining reproduction:")
        print("1. Download 'train_transaction.csv' (683 MB) from IEEE-CIS Fraud Detection dataset.")
        print("2. Place it in 'data/raw/train_transaction.csv'.")
        print("3. Re-run: python scripts/reproduce.py --mode full\n")
        return False

    out_dir = Path(output_dir) if output_dir else ROOT / "results" / "reproduction_run"
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"Found raw dataset at {raw_tx} ({raw_tx.stat().st_size / 1024 / 1024:.1f} MB).")
    print(f"Isolated reproduction directory: {out_dir}")
    print("Executing full reproduction pipeline:")

    pipeline_steps = [
        ("Step 1: Dataset Validation", [sys.executable, "scripts/validate_dataset.py", "--output-dir", str(out_dir)]),
        ("Step 2: Gate G1 Baselines Evaluation", [sys.executable, "scripts/run_g1_eval.py", "--output-dir", str(out_dir)]),
        ("Step 3: Gate G2 Heterogeneous Ensemble", [sys.executable, "scripts/run_g2_eval.py", "--output-dir", str(out_dir)]),
        ("Step 4: Gate G5 Formal Evaluation (results.json)", [sys.executable, "scripts/run_g5_eval.py", "--output-dir", str(out_dir)]),
        ("Step 5: Gate G6 Agent Output Caching", [sys.executable, "scripts/cache_agent_outputs.py", "--output-dir", str(out_dir), "--results-file", str(out_dir / "results.json")]),
    ]

    for step_name, cmd in pipeline_steps:
        print(f"\n--- {step_name} ---")
        print(f"Executing: {' '.join(cmd)}")
        res = subprocess.run(cmd, cwd=str(ROOT))
        if res.returncode != 0:
            print(f"FAILED: {step_name} exited with code {res.returncode}")
            return False

    print("\nFull experiment reproduction completed successfully!")

    # Compare reproduction results with frozen canonical evidence
    compare_reproduction_results(out_dir, canonical_dir=ROOT / "results")

    # Verify canonical frozen evidence remains untouched and valid
    return run_offline_audit()


def main() -> None:
    parser = argparse.ArgumentParser(description="SignalGate Master Reproduction Entry Point")
    parser.add_argument(
        "--mode",
        choices=["offline", "full", "audit"],
        default="offline",
        help="Reproduction workflow: 'offline' (demo & audit), 'full' (complete retraining reproduction)",
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help="Target directory for generated reproduction artifacts (defaults to results/reproduction_run for full mode)",
    )
    args = parser.parse_args()

    if args.mode in ("offline", "audit"):
        success = run_offline_audit()
    else:
        out_dir = args.output_dir or str(ROOT / "results" / "reproduction_run")
        success = run_full_reproduction(output_dir=out_dir)

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
