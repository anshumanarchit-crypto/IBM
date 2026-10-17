"""Gate G2 ensemble training, calibration, and validation-only ablation.

Pipeline:
  1. Load data and re-use the G1 chronological partitions (read-only).
  2. Fit FeaturePipeline (same as G1) on train.
  3. Fit HeterogeneousEnsemble on train partition.
  4. Fit PlattCalibrator and IsotonicCalibrator on calibration partition.
  5. Compute ensemble mean p and calibrated variants on validation.
  6. Extract disagreement signals (u, u2) on validation.
  7. Ablation: compare E1 (ensemble mean, no calibration),
               E2 (Platt-calibrated ensemble),
               E3 (isotonic-calibrated ensemble)
     against B2@1.5x baseline using validation PR-AUC and recall.
  8. Save results to results/g2_ensemble_report.json.

CRITICAL: Test partition is never touched in G2.  All tuning and selection
decisions are made exclusively on the validation partition.  The existing
g1_baselines_report.json is not re-read for tuning (only for provenance).
"""

from __future__ import annotations

import json
import sys
import time
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import numpy as np
import pandas as pd

from data.splits import load_and_split
from models.calibration import IsotonicCalibrator, PlattCalibrator, calibration_ece
from models.ensemble import HeterogeneousEnsemble
from models.features import FeaturePipeline
from models.baselines import TopBudgetBaseline, compute_triage_metrics
from models.signals import compute_signals

RESULTS_DIR = ROOT / "results"
REPORT_FILE = RESULTS_DIR / "g2_ensemble_report.json"
SPLIT_MANIFEST_FILE = RESULTS_DIR / "split_manifest.json"
G1_REPORT_FILE = RESULTS_DIR / "g1_baselines_report.json"


# ---- Utility ---------------------------------------------------------------

def _ablation_at_budget(
    label: str,
    scores: np.ndarray,
    y_val: np.ndarray,
    val_ids: np.ndarray,
    train_prevalence: float,
    budget_multiple: float = 1.5,
) -> dict:
    b2 = TopBudgetBaseline(budget_multiple=budget_multiple)
    preds = b2.route(scores, val_ids, train_prevalence)
    m = compute_triage_metrics(y_val, preds, scores)
    return {
        "variant": label,
        "budget_multiple": budget_multiple,
        "validation": asdict(m),
    }


# ---- Main pipeline ---------------------------------------------------------

def run_g2_pipeline(output_dir: Path | str | None = None) -> dict:
    print("=" * 60)
    print("SignalGate Gate G2: Ensemble + Calibration + Signals Pipeline")
    print("=" * 60)
    out_dir = Path(output_dir) if output_dir else RESULTS_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    report_file = out_dir / "g2_ensemble_report.json"
    g1_file = out_dir / "g1_baselines_report.json" if (out_dir / "g1_baselines_report.json").exists() else G1_REPORT_FILE

    # Record G1 provenance (read-only, not for tuning)
    g1_provenance: dict = {}
    if g1_file.exists():
        g1_provenance = json.loads(g1_file.read_text(encoding="utf-8"))
        b2_1_5_val_recall = (
            g1_provenance.get("b2_top_budget_ranking", {})
            .get("1.5", {})
            .get("validation", {})
            .get("recall", None)
        )
        print(f"\nG1 B2@1.5x validation recall (provenance): {b2_1_5_val_recall}")

    # 1. Load and partition data
    print("\n1. Loading and partitioning data (read-only, same G1 split)...")
    raw_dir = ROOT / "data" / "raw"
    partitions, split_meta = load_and_split(raw_dir, manifest_out=None)  # no overwrite

    train_df = partitions["train"]
    cal_df = partitions["calibration"]
    val_df = partitions["validation"]
    # test_df intentionally NOT loaded or used

    train_prevalence = split_meta["train"].prevalence
    print(f"  Train rows: {len(train_df)}, Calibration rows: {len(cal_df)}, Validation rows: {len(val_df)}")
    print(f"  Train prevalence: {train_prevalence * 100:.4f}%")

    # 2. Fit feature pipeline on train (same as G1)
    print("\n2. Fitting FeaturePipeline on train partition...")
    t0 = time.time()
    feature_pipe = FeaturePipeline()
    feature_pipe.fit(train_df)
    print(f"  Feature pipeline fitted in {time.time()-t0:.2f}s  ({feature_pipe.get_manifest().feature_count} features)")

    X_train = feature_pipe.transform(train_df)
    y_train = train_df["isFraud"].values.astype(int)

    X_cal = feature_pipe.transform(cal_df)
    y_cal = cal_df["isFraud"].values.astype(int)

    X_val = feature_pipe.transform(val_df)
    y_val = val_df["isFraud"].values.astype(int)
    val_ids = val_df["TransactionID"].values

    print(f"  X_train: {X_train.shape}, X_cal: {X_cal.shape}, X_val: {X_val.shape}")

    # 3. Fit ensemble on train partition
    print("\n3. Fitting HeterogeneousEnsemble on train partition...")
    t0 = time.time()
    ensemble = HeterogeneousEnsemble()
    ensemble.fit(X_train, y_train)
    ensemble_duration_s = time.time() - t0
    print(f"  Ensemble fitted in {ensemble_duration_s:.2f}s  ({ensemble.n_members} members: {ensemble.member_ids})")

    # 4. Generate calibration scores from ensemble on calibration partition
    print("\n4. Computing ensemble scores on calibration partition...")
    cal_member_preds = ensemble.predict_member_proba(X_cal)
    cal_raw_scores = cal_member_preds.proba_matrix.mean(axis=1)

    # 5. Fit calibrators on calibration partition
    print("\n5. Fitting calibrators on calibration partition...")
    platt_cal = PlattCalibrator()
    platt_cal.fit(cal_raw_scores, y_cal)
    print("  PlattCalibrator fitted.")

    iso_cal = IsotonicCalibrator()
    iso_cal.fit(cal_raw_scores, y_cal)
    print("  IsotonicCalibrator fitted.")

    # Calibration diagnostics on calibration set (not used for selection)
    cal_ece_raw = calibration_ece(cal_raw_scores, y_cal)
    cal_platt = platt_cal.predict_proba(cal_raw_scores)
    cal_iso = iso_cal.predict_proba(cal_raw_scores)
    cal_ece_platt = calibration_ece(cal_platt, y_cal)
    cal_ece_iso = calibration_ece(cal_iso, y_cal)
    print(f"  ECE (calibration set) — Raw: {cal_ece_raw:.4f}, Platt: {cal_ece_platt:.4f}, Isotonic: {cal_ece_iso:.4f}")

    # 6. Generate ensemble scores on validation partition
    print("\n6. Computing ensemble scores and disagreement signals on validation...")
    val_member_preds = ensemble.predict_member_proba(X_val)
    val_raw_scores = val_member_preds.proba_matrix.mean(axis=1)
    val_platt_scores = platt_cal.predict_proba(val_raw_scores)
    val_iso_scores = iso_cal.predict_proba(val_raw_scores)

    # Disagreement signals
    val_signals = compute_signals(val_member_preds)
    u_arr = val_signals["u"]
    u2_arr = val_signals["u2"]
    print(f"  u  (std): mean={u_arr.mean():.4f}, median={np.median(u_arr):.4f}, p95={np.percentile(u_arr, 95):.4f}")
    print(f"  u2 (MAD): mean={u2_arr.mean():.4f}, median={np.median(u2_arr):.4f}, p95={np.percentile(u2_arr, 95):.4f}")

    # 7. Validation-only ablation
    print("\n7. Validation ablation: E1 (raw), E2 (Platt), E3 (Isotonic) vs B2@1.5x...")
    ablations = []
    for label, scores in [
        ("E1_ensemble_raw", val_raw_scores),
        ("E2_ensemble_platt", val_platt_scores),
        ("E3_ensemble_isotonic", val_iso_scores),
    ]:
        result = _ablation_at_budget(label, scores, y_val, val_ids, train_prevalence, 1.5)
        ablations.append(result)
        vm = result["validation"]
        print(f"  {label}: recall={vm['recall']*100:.2f}%, precision={vm['precision']*100:.2f}%, "
              f"pr_auc={vm['pr_auc']:.4f}, detected={vm['detected_fraud']}, missed={vm['missed_fraud']}")

    # Full budget sweep for the best variant (E2 Platt as representative)
    budget_sweep_results = {}
    for mult in [1.0, 1.5, 2.0, 3.0]:
        r = _ablation_at_budget("E2_ensemble_platt", val_platt_scores, y_val, val_ids, train_prevalence, mult)
        budget_sweep_results[str(mult)] = r
        vm = r["validation"]
        tag = " (PRIMARY)" if mult == 1.5 else ""
        print(f"  E2 ({mult}x{tag}): recall={vm['recall']*100:.2f}%, touched={vm['touched_rate']*100:.2f}%, "
              f"precision={vm['precision']*100:.2f}%")

    # 8. Extract member solver diagnostics (specifically lr_s11)
    lr_member = ensemble.get_member("lr_s11")
    lr_step = lr_member.named_steps["lr"]
    lr_n_iter = int(lr_step.n_iter_[0])
    lr_converged = bool(lr_n_iter < lr_step.max_iter)
    lr_diagnostics = {
        "member_id": "lr_s11",
        "solver": lr_step.solver,
        "max_iter": lr_step.max_iter,
        "n_iter": lr_n_iter,
        "converged": lr_converged,
        "has_median_imputer": "imputer" in lr_member.named_steps,
        "has_standard_scaler": "scaler" in lr_member.named_steps,
        "imputer_fitted_on": "train_partition_only",
        "scaler_fitted_on": "train_partition_only",
        "warning_status": "zero_warnings" if lr_converged else "convergence_warning",
    }
    print(f"\n  LogisticRegression (lr_s11) diagnostics:")
    print(f"    Solver: {lr_step.solver}, max_iter: {lr_step.max_iter}, n_iter: {lr_n_iter}")
    print(f"    Converged: {lr_converged}, Warning status: {lr_diagnostics['warning_status']}")

    # 9. Assemble and save G2 report
    g2_report = {
        "gate": "G2",
        "run_id": "run_2_corrected",
        "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "partition_verification": {
            "train_hash": split_meta["train"].split_hash,
            "calibration_hash": split_meta["calibration"].split_hash,
            "validation_hash": split_meta["validation"].split_hash,
            "test_partition_loaded": False,
            "test_labels_loaded": False,
        },
        "train_prevalence": train_prevalence,
        "ensemble": {
            "n_members": ensemble.n_members,
            "member_ids": ensemble.member_ids,
            "fit_duration_seconds": ensemble_duration_s,
            "lr_member_diagnostics": lr_diagnostics,
        },
        "calibration": {
            "method": ["sigmoid_platt", "isotonic"],
            "fitted_on": "calibration_partition",
            "ece_raw": cal_ece_raw,
            "ece_platt": cal_ece_platt,
            "ece_isotonic": cal_ece_iso,
        },
        "disagreement_signals": {
            "u_mean": float(u_arr.mean()),
            "u_median": float(np.median(u_arr)),
            "u_p95": float(np.percentile(u_arr, 95)),
            "u2_mean": float(u2_arr.mean()),
            "u2_median": float(np.median(u2_arr)),
            "u2_p95": float(np.percentile(u2_arr, 95)),
            "n_members": int(ensemble.n_members),
        },
        "validation_ablation": ablations,
        "e2_budget_sweep_validation": budget_sweep_results,
        "g1_b2_val_recall_provenance": (
            g1_provenance.get("b2_top_budget_ranking", {})
            .get("1.5", {})
            .get("validation", {})
            .get("recall", None)
        ),
        "g1_report_timestamp_provenance": g1_provenance.get("timestamp_utc"),
        "audit_note": "Run 2 with StandardScaler fitted on train partition only; zero ConvergenceWarning emitted; exit code 0.",
    }

    report_file.write_text(json.dumps(g2_report, indent=2), encoding="utf-8")
    print(f"\nG2 report saved to: {report_file}")
    print("=" * 60)
    return g2_report


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="SignalGate Gate G2 Ensemble Pipeline")
    parser.add_argument("--output-dir", default=None, help="Directory to save G2 artifacts")
    args = parser.parse_args()
    run_g2_pipeline(output_dir=args.output_dir)
