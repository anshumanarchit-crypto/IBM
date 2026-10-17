# Gate G1 Readiness Report: Dataset Validation, Chronological Partitioning, and Risk-Only Baselines
## SignalGate: Shift-Aware Fraud Triage for IBM Z Datathon 2026

**Date:** 2026-10-17  
**Status:** **PASS** (G1 Complete — Ready for Review; G2 Halted)  
**Target Platform:** IBM Z / LinuxONE (Simulation on AMD64)  
**Evaluation Scope:** Baseline B1 and B2 under Workload Constraints on IEEE-CIS Labeled Transactions  

---

## 1. Executive Summary

Gate G1 establishes the empirical dataset foundation, leakage-safe chronological partitioning, feature preprocessing manifest, and primary risk-only baseline (B2) for SignalGate.

All components adhere strictly to the non-negotiable architectural boundaries:
- **Ground Truth Isolation**: Target label `isFraud` and identifiers (`TransactionID`, raw `TransactionDT`) are excluded from model inputs.
- **Strict Chronological Ordering**: Partitions strictly respect temporal order ($60\%$ train, $10\%$ calibration, $10\%$ validation, $20\%$ test) with zero temporal overlap.
- **Deterministic Workload Constraints**: B2 top-budget ranking enforces review volume matched to multiples of training fraud prevalence ($1.0\times, 1.5\times, 2.0\times, 3.0\times$).
- **No Early G2 Progression**: No disagreement signals, LLM agents, or TEE attestations were implemented in G1.
- **Preserved G0 Integrity**: All 12 G0 tests remain passing; 9 new G1 tests were added, bringing the total passing test suite to **21 passed, 0 failures**.

---

## 2. Dataset Validation Audit

The IEEE-CIS Fraud Detection dataset located in `data/raw/` was cryptographically hashed and inspected:

### Raw File Integrity & SHA-256 Hashes
| File Name | File Size (Bytes) | SHA-256 Checksum | Labeled? |
| :--- | :--- | :--- | :--- |
| `train_transaction.csv` | 683,351,067 | `3a5c83ab6b3cc13dcabe5ffa9f522307fd5f7f7b6e6f6a60c32284ca6283d642` | Yes (Source) |
| `train_identity.csv` | 26,529,680 | `b63c725d8377be90a995268d97f347c17d456b95db45807adcf9f59cd603c37c` | Metadata |
| `test_transaction.csv` | 613,194,934 | `2a8e51f1d335a86025d2b7f45beb9b78d0ab1edd726ef531d8b71a8a0065c011` | No (Unlabeled) |
| `test_identity.csv` | 25,797,161 | `3e5978cb13ca5e72f52babc4349ae0125e14b87ca8bfabe952ab67bb4ff1e10b` | No (Unlabeled) |
| `sample_submission.csv` | 6,080,314 | `50d7e0d6fcfc6e498efc297001f252101512ccdcb34aefbde6db98f8242a3626` | No |

> [!IMPORTANT]
> **Internal Benchmark Isolation Notice**: `test_transaction.csv` does not supply ground truth fraud labels (`isFraud`). Under no circumstances is the Kaggle competition test file used as the internal labeled evaluation set. The labeled source is strictly `train_transaction.csv`.

### Labeled Transaction Properties (`train_transaction.csv`)
- **Total Rows**: 590,540
- **Total Columns**: 394
- **Identifier Uniqueness**: `TransactionID` is 100% unique (range: `2987000` to `3577539`).
- **Timestamp Coverage**: `TransactionDT` spans **182.0 days** (min: `86,400`, max: `15,811,131`). Sorted monotonically increasing.
- **Target Distribution (`isFraud`)**:
  - Non-Fraud (`0`): 569,877 (96.501%)
  - Fraud (`1`): 20,663 (3.499%)
  - Overall Fraud Prevalence: **3.4990%**

### Identity Join Audit (`train_identity.csv`)
- **Identity Rows**: 144,233 (41 columns)
- **Left Join Preservation**: Performing `train_transaction LEFT JOIN train_identity ON TransactionID` produces exactly **590,540 rows** (zero duplication, zero dropped rows).
- **Identity Coverage**: 144,233 transactions (24.42%) have identity records; 446,307 (75.58%) are anonymous.

---

## 3. Leakage-Safe Chronological Partitioning (`data/splits.py`)

In accordance with [config.yaml](file:///c:/Users/archi/OneDrive/Desktop/SignalGate/config.yaml), transactions were chronologically sorted by `TransactionDT` and partitioned into 4 disjoint intervals:

| Partition | Share | Row Count | Fraud Cases | Prevalence | `TransactionDT` Interval | Partition Hash (SHA-256) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Train** | 60% | 354,324 | 11,988 | 3.3833% | `[86,400, 8,745,772]` | `ee8c38fd7e8b2af1...` |
| **Calibration** | 10% | 59,054 | 2,550 | 4.3181% | `[8,745,798, 10,437,996]` | `a1880e4f36558c33...` |
| **Validation** | 10% | 59,054 | 2,061 | 3.4900% | `[10,438,003, 12,192,842]` | `f824d80aea2e20f7...` |
| **Held-Out Test** | 20% | 118,108 | 4,064 | 3.4409% | `[12,192,900, 15,811,131]` | `88d73a15fc60f9ba...` |
| **Total** | 100% | **590,540** | **20,663** | **3.4990%** | `[86,400, 15,811,131]` | — |

### Verification of Temporal Disjointness:
- $\max(\text{Train DT}) = 8,745,772 < 8,745,798 = \min(\text{Calibration DT})$
- $\max(\text{Calibration DT}) = 10,437,996 < 10,438,003 = \min(\text{Validation DT})$
- $\max(\text{Validation DT}) = 12,192,842 < 12,192,900 = \min(\text{Test DT})$
- **Result**: Zero temporal leakage across all boundaries.

---

## 4. Feature Pipeline & Learned Preprocessing (`models/features.py`)

- **Explicit Exclusions**: `['TransactionID', 'TransactionDT', 'isFraud']` are strictly excluded from feature matrices.
- **Learned Transformers**: Preprocessing fitted **exclusively on the training partition** ($354,324$ rows).
- **Features Extracted**:
  - **377 Numerical Features** (normalized and handled natively by gradient boosted tree histogram binning).
  - **14 Categorical Features** (`ProductCD`, `card4`, `card6`, `P_emaildomain`, `R_emaildomain`, `M1`–`M9`) encoded via `OrdinalEncoder(handle_unknown='use_encoded_value', unknown_value=-1)`.
  - **Total Features**: **391 features**.
- Saved to [results/feature_manifest.json](file:///c:/Users/archi/OneDrive/Desktop/SignalGate/results/feature_manifest.json).

---

## 5. Risk-Only Baseline Benchmarks (`models/baselines.py`)

### Model Architecture
- **Model**: `HistGradientBoostingClassifier(random_state=11, max_iter=60, class_weight='balanced')`
- **Training Duration**: $19.42$ seconds on $354,324$ train rows.

### Baseline B1: Fixed Risk Threshold
- Threshold selected solely on validation partition to target $1.5\times$ training prevalence review budget ($5.075\%$): $\tau^* = 0.6936$.
- **Validation**: Recall = $57.11\%$, Touched Rate = $5.08\%$, Precision = $39.27\%$, PR-AUC = $0.5234$.
- **Held-Out Test**: Recall = $52.61\%$, Touched Rate = **$5.69\%$**, Precision = $31.82\%$, PR-AUC = $0.4522$.
- *Finding*: Fixed threshold review volume drifted from $5.08\%$ to $5.69\%$ on test data due to score distribution shifts, confirming the need for workload-matched ranking (B2).

### Baseline B2: Top-Budget Ranking (Primary Comparator)
Under B2, transactions are ranked descending by predicted risk $\hat{p}$ with **deterministic secondary sorting by `TransactionID` ascending** for tie handling. Transactions are escalated up to the exact review budget $B = M \times \text{prevalence}_{\text{train}} \times N$:

| Multiple | Target Touched | Val Touched | Val Recall | Val Precision | Val Detected / Missed | Test Touched | Test Recall | Test Precision | Test Detected / Missed | Test PR-AUC |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **$1.0\times$** | 3.383% | 3.383% | 49.25% | 50.80% | 1,015 / 1,046 | 3.383% | 43.53% | 44.27% | 1,769 / 2,295 | 0.4522 |
| **$1.5\times$ (PRIMARY)** | **5.075%** | **5.075%** | **57.11%** | **39.27%** | **1,177 / 884** | **5.075%** | **50.52%** | **34.25%** | **2,053 / 2,011** | **0.4522** |
| **$2.0\times$** | 6.767% | 6.767% | 62.64% | 32.31% | 1,291 / 770 | 6.767% | 55.44% | 28.19% | 2,253 / 1,811 | 0.4522 |
| **$3.0\times$** | 10.150% | 10.150% | 70.26% | 24.16% | 1,448 / 613 | 10.150% | 63.36% | 21.48% | 2,575 / 1,489 | 0.4522 |

> [!NOTE]
> **Primary Evaluation Benchmark**: B2 at $1.5\times$ review budget achieves **$50.52\%$ recall** (2,053 frauds caught, 2,011 missed out of 4,064) on the held-out test set at an exact $5.075\%$ review workload ($5,994$ transactions inspected). This established B2 benchmark will serve as the exact comparator for future SignalGate shift-aware triage experiments.

---

## 6. Gate G1 Exit Criteria Checklist

| Gate Requirement | Verification Method | Status |
| :--- | :--- | :--- |
| **Dataset Validation** | Real CSV schemas, hashes, and join integrity audited in [results/dataset_validation_report.json](file:///c:/Users/archi/OneDrive/Desktop/SignalGate/results/dataset_validation_report.json). | **PASS** |
| **Chronological Partitions** | 60/10/10/20 split executed in [data/splits.py](file:///c:/Users/archi/OneDrive/Desktop/SignalGate/data/splits.py); verified disjoint intervals in [results/split_manifest.json](file:///c:/Users/archi/OneDrive/Desktop/SignalGate/results/split_manifest.json). | **PASS** |
| **Feature Leakage Prevention** | `isFraud`, `TransactionID`, and `TransactionDT` barred from feature manifest; verified in unit tests. | **PASS** |
| **Learned Preprocessing Isolation** | Fitted solely on train partition; handles unseen test categories with fixed defaults. | **PASS** |
| **B1 & B2 Implementations** | Fixed threshold and top-budget ranking implemented in [models/baselines.py](file:///c:/Users/archi/OneDrive/Desktop/SignalGate/models/baselines.py). | **PASS** |
| **Deterministic Tie Handling** | Secondary sort on `TransactionID` verified byte-identical. | **PASS** |
| **Budget Sweep Execution** | Evaluated at $1.0\times, 1.5\times, 2.0\times, 3.0\times$; documented in [results/g1_baselines_report.json](file:///c:/Users/archi/OneDrive/Desktop/SignalGate/results/g1_baselines_report.json). | **PASS** |
| **Test Suite Integrity** | Full test suite passed (12 G0 tests + 9 G1 tests = 21 passing tests). | **PASS** |
| **No Premature G2 Features** | Model disagreement signals, LLM agents, and TEE attestation intentionally omitted in G1. | **PASS** |
| **Hardware Attestation Claim** | Honest reporting: IBM Secure Execution not measured on local AMD64 workstation. | **NOT MEASURED** |

---

## 7. Test Suite Execution Evidence

Command executed:
```powershell
python -m pytest -ra
```

Output:
```text
tests/test_agent_guardrails.py ..                                        [  9%]
tests/test_agent_view.py ..                                              [ 19%]
tests/test_audit_chain.py ....                                           [ 38%]
tests/test_baselines.py .....                                            [ 61%]
tests/test_scaffolding.py ....                                           [ 80%]
tests/test_splits.py ....                                                [100%]

============================== 21 passed in 4.64s ==============================
```

---

## 8. Gate G1 Conclusion

Gate G1 is **COMPLETE** and verified. Work is halted at G1. Awaiting human review before proceeding to Gate G2.
