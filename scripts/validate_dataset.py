"""Validate the IEEE-CIS Fraud Detection raw dataset in data/raw/."""

import hashlib
import json
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw"
REPORT_PATH = ROOT / "results" / "dataset_validation_report.json"


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(chunk_size):
            hasher.update(chunk)
    return hasher.hexdigest()


def validate_raw_data(output_dir: Path | str | None = None) -> dict:
    print("Starting dataset validation...")
    out_dir = Path(output_dir) if output_dir else REPORT_PATH.parent
    out_dir.mkdir(parents=True, exist_ok=True)
    report_path = out_dir / "dataset_validation_report.json"

    files = [
        "train_transaction.csv",
        "train_identity.csv",
        "test_transaction.csv",
        "test_identity.csv",
        "sample_submission.csv",
    ]

    report = {
        "files": {},
        "train_transaction_validation": {},
        "join_validation": {},
    }

    # 1. Inspect file presence, size, and SHA256 hashes
    for fname in files:
        fpath = RAW_DIR / fname
        if not fpath.exists():
            raise FileNotFoundError(f"Missing required raw file: {fpath}")
        size = fpath.stat().st_size
        print(f"Hashing {fname} ({size / (1024*1024):.1f} MB)...")
        file_hash = sha256_file(fpath)
        report["files"][fname] = {
            "size_bytes": size,
            "sha256": file_hash,
        }
        print(f"  {fname}: {file_hash[:16]}... (size: {size} bytes)")

    # 2. Inspect train_transaction.csv
    print("\nLoading train_transaction.csv (memory-conscious)...")
    # Read core columns first for fast metadata
    df_tx = pd.read_csv(RAW_DIR / "train_transaction.csv")
    row_count, col_count = df_tx.shape
    print(f"train_transaction shape: {row_count} rows, {col_count} columns")

    id_unique = bool(df_tx["TransactionID"].is_unique)
    min_id = int(df_tx["TransactionID"].min())
    max_id = int(df_tx["TransactionID"].max())

    min_dt = int(df_tx["TransactionDT"].min())
    max_dt = int(df_tx["TransactionDT"].max())
    dt_span_days = (max_dt - min_dt) / 86400.0
    dt_is_monotonic = bool(df_tx["TransactionDT"].is_monotonic_increasing)

    fraud_counts = df_tx["isFraud"].value_counts().to_dict()
    total_fraud = int(fraud_counts.get(1, 0))
    total_legit = int(fraud_counts.get(0, 0))
    prevalence = float(total_fraud / row_count)

    report["train_transaction_validation"] = {
        "rows": row_count,
        "columns": col_count,
        "transaction_id_unique": id_unique,
        "transaction_id_range": [min_id, max_id],
        "transaction_dt_min": min_dt,
        "transaction_dt_max": max_dt,
        "transaction_dt_span_days": dt_span_days,
        "transaction_dt_is_monotonic": dt_is_monotonic,
        "isFraud_counts": {0: total_legit, 1: total_fraud},
        "isFraud_prevalence": prevalence,
    }
    print(f"  Fraud prevalence: {prevalence * 100:.3f}% ({total_fraud} frauds / {row_count} rows)")
    print(f"  TransactionDT span: {dt_span_days:.1f} days (min: {min_dt}, max: {max_dt})")
    print(f"  TransactionDT monotonically sorted: {dt_is_monotonic}")

    # 3. Inspect train_identity.csv and test join
    print("\nLoading train_identity.csv...")
    df_id = pd.read_csv(RAW_DIR / "train_identity.csv")
    id_rows, id_cols = df_id.shape
    id_unique_in_identity = bool(df_id["TransactionID"].is_unique)
    print(f"train_identity shape: {id_rows} rows, {id_cols} columns")
    print(f"TransactionID unique in train_identity: {id_unique_in_identity}")

    # Validate Left Join
    print("Testing left join: train_transaction LEFT JOIN train_identity ON TransactionID...")
    merged = pd.merge(df_tx[["TransactionID", "TransactionDT", "isFraud"]], df_id, on="TransactionID", how="left")
    merged_rows = len(merged)
    join_preserves_rows = (merged_rows == row_count)
    has_identity_count = int(merged["id_01"].notna().sum()) if "id_01" in merged.columns else int(df_id["TransactionID"].isin(df_tx["TransactionID"]).sum())
    identity_coverage_pct = float(has_identity_count / row_count)

    report["join_validation"] = {
        "train_identity_rows": id_rows,
        "train_identity_columns": id_cols,
        "train_identity_id_unique": id_unique_in_identity,
        "left_join_preserves_row_count": join_preserves_rows,
        "left_join_result_rows": merged_rows,
        "transactions_with_identity": has_identity_count,
        "identity_coverage_pct": identity_coverage_pct,
    }
    print(f"  Left join preserves rows: {join_preserves_rows} ({merged_rows} == {row_count})")
    print(f"  Transactions with identity metadata: {has_identity_count} ({identity_coverage_pct * 100:.2f}%)")

    # Save validation report
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"\nValidation report saved to: {report_path}")
    return report


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Validate IEEE-CIS raw dataset")
    parser.add_argument("--output-dir", default=None, help="Directory to save dataset_validation_report.json")
    args = parser.parse_args()
    validate_raw_data(output_dir=args.output_dir)
