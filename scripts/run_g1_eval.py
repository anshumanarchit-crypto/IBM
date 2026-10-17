"""Execute Gate G1 baseline training, validation, and evaluation on IEEE-CIS data.

Enforces:
1. Pure chronological split (train 60%, calibration 10%, validation 10%, test 20%).
2. Preprocessing learned solely from train partition.
3. Target column isFraud and identifiers (TransactionID, TransactionDT) excluded from features.
4. B1 fixed threshold and B2 top-budget ranking evaluated across budget sweep.
5. All results saved to results/g1_baselines_report.json.
"""

from __future__ import annotations

import json
from dataclasses import asdict
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import time
import pandas as pd
import numpy as np

from data.splits import load_and_split
from models.features import FeaturePipeline
from models.baselines import (
    RiskEstimator,
    FixedThresholdBaseline,
    TopBudgetBaseline,
    compute_triage_metrics,
)

ROOT = Path(__file__).resolve().parents[1]
RESULTS_DIR = ROOT / "results"
REPORT_FILE = RESULTS_DIR / "g1_baselines_report.json"
FEATURE_MANIFEST_FILE = RESULTS_DIR / "feature_manifest.json"
SPLIT_MANIFEST_FILE = RESULTS_DIR / "split_manifest.json"


def run_g1_pipeline(output_dir: Path | str | None = None) -> dict:
    print("=" * 60)
    print("SignalGate Gate G1: Baseline Evaluation Pipeline")
    print("=" * 60)
    out_dir = Path(output_dir) if output_dir else RESULTS_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    report_file = out_dir / "g1_baselines_report.json"
    feature_manifest_file = out_dir / "feature_manifest.json"
    split_manifest_file = out_dir / "split_manifest.json"

    # 1. Load data & partition chronologically
    print("\n1. Partitioning labeled transactions chronologically...")
    raw_dir = ROOT / "data" / "raw"
    partitions, split_meta = load_and_split(raw_dir, manifest_out=split_manifest_file)

    train_df = partitions["train"]
    cal_df = partitions["calibration"]
    val_df = partitions["validation"]
    test_df = partitions["test"]

    train_prevalence = split_meta["train"].prevalence
    print(f"  Train prevalence: {train_prevalence * 100:.3f}% ({split_meta['train'].fraud_count} / {split_meta['train'].row_count})")
    print(f"  Validation rows:  {len(val_df)} (fraud: {split_meta['validation'].fraud_count})")
    print(f"  Test rows:        {len(test_df)} (fraud: {split_meta['test'].fraud_count})")

    # 2. Fit feature pipeline solely on train
    print("\n2. Fitting feature pipeline strictly on train partition...")
    t0 = time.time()
    feature_pipe = FeaturePipeline()
    feature_pipe.fit(train_df)
    feature_pipe.save_manifest(feature_manifest_file)
    manifest = feature_pipe.get_manifest()
    print(f"  Learned {manifest.feature_count} features ({len(manifest.numerical_columns)} numerical, {len(manifest.categorical_columns)} categorical)")
    print(f"  Excluded columns: {manifest.excluded_columns}")
    print(f"  Preprocessing fitted in {time.time() - t0:.2f}s")

    # 3. Transform partitions
    print("\n3. Transforming feature matrices...")
    X_train = feature_pipe.transform(train_df)
    y_train = train_df["isFraud"].values.astype(int)

    X_val = feature_pipe.transform(val_df)
    y_val = val_df["isFraud"].values.astype(int)
    val_ids = val_df["TransactionID"].values

    X_test = feature_pipe.transform(test_df)
    y_test = test_df["isFraud"].values.astype(int)
    test_ids = test_df["TransactionID"].values
    print(f"  X_train: {X_train.shape}, X_val: {X_val.shape}, X_test: {X_test.shape}")

    # 4. Fit RiskEstimator on train partition
    print("\n4. Fitting RiskEstimator (sklearn HistGradientBoostingClassifier) on train...")
    t0 = time.time()
    risk_model = RiskEstimator(random_state=11, max_iter=60)
    risk_model.fit(X_train, y_train)
    fit_duration_s = time.time() - t0
    print(f"  Model trained in {fit_duration_s:.2f}s")

    # 5. Predict risk scores
    print("\n5. Computing predicted risk scores...")
    val_scores = risk_model.predict_proba(X_val)
    test_scores = risk_model.predict_proba(X_test)

    # 6. Evaluate Baseline B1: Fixed threshold (tuned on validation)
    print("\n6. Evaluating Baseline B1 (Fixed Threshold)...")
    b1 = FixedThresholdBaseline()
    primary_budget_multiple = 1.5
    target_budget_rate = primary_budget_multiple * train_prevalence
    b1_threshold = b1.select_threshold_on_validation(y_val, val_scores, target_touched_rate=target_budget_rate)
    print(f"  Selected validation threshold: {b1_threshold:.4f} (target rate: {target_budget_rate*100:.3f}%)")

    b1_val_preds = b1.route(val_scores)
    b1_val_metrics = compute_triage_metrics(y_val, b1_val_preds, val_scores)

    b1_test_preds = b1.route(test_scores)
    b1_test_metrics = compute_triage_metrics(y_test, b1_test_preds, test_scores)

    print(f"  B1 Validation: recall={b1_val_metrics.recall*100:.2f}%, touched={b1_val_metrics.touched_rate*100:.2f}%, prec={b1_val_metrics.precision*100:.2f}%, pr_auc={b1_val_metrics.pr_auc:.4f}")
    print(f"  B1 Test:       recall={b1_test_metrics.recall*100:.2f}%, touched={b1_test_metrics.touched_rate*100:.2f}%, prec={b1_test_metrics.precision*100:.2f}%, pr_auc={b1_test_metrics.pr_auc:.4f}")

    # 7. Evaluate Baseline B2: Top-budget ranking across budget sweep
    print("\n7. Evaluating Baseline B2 (Risk-Only Top-Budget Ranking)...")
    budget_sweeps = [1.0, 1.5, 2.0, 3.0]
    b2_results = {}

    for mult in budget_sweeps:
        b2 = TopBudgetBaseline(budget_multiple=mult)
        val_preds = b2.route(val_scores, val_ids, train_prevalence)
        val_m = compute_triage_metrics(y_val, val_preds, val_scores)

        test_preds = b2.route(test_scores, test_ids, train_prevalence)
        test_m = compute_triage_metrics(y_test, test_preds, test_scores)

        b2_results[str(mult)] = {
            "budget_multiple": mult,
            "validation": asdict(val_m),
            "test": asdict(test_m),
        }
        tag = "(PRIMARY)" if mult == 1.5 else ""
        print(f"  B2 ({mult}x {tag}):")
        print(f"    Val:  recall={val_m.recall*100:5.2f}%, touched={val_m.touched_rate*100:5.2f}%, prec={val_m.precision*100:5.2f}%, detected={val_m.detected_fraud:4d}, missed={val_m.missed_fraud:4d}")
        print(f"    Test: recall={test_m.recall*100:5.2f}%, touched={test_m.touched_rate*100:5.2f}%, prec={test_m.precision*100:5.2f}%, detected={test_m.detected_fraud:4d}, missed={test_m.missed_fraud:4d}")

    # 8. Assemble and save G1 report
    g1_report = {
        "gate": "G1",
        "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "train_prevalence": train_prevalence,
        "feature_count": manifest.feature_count,
        "fit_duration_seconds": fit_duration_s,
        "b1_fixed_threshold": {
            "threshold": b1_threshold,
            "target_rate": target_budget_rate,
            "validation": asdict(b1_val_metrics),
            "test": asdict(b1_test_metrics),
        },
        "b2_top_budget_ranking": b2_results,
    }

    report_file.write_text(json.dumps(g1_report, indent=2), encoding="utf-8")
    print(f"\nG1 report saved to: {report_file}")
    print("=" * 60)
    return g1_report


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="SignalGate Gate G1 Baseline Pipeline")
    parser.add_argument("--output-dir", default=None, help="Directory to save G1 artifacts")
    args = parser.parse_args()
    run_g1_pipeline(output_dir=args.output_dir)
