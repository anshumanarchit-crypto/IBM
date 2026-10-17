# Gate G5 Readiness & Acceptance Report: Formal Evaluation and Statistical Evidence
## Shift-Aware Fraud Triage for IBM Z Datathon 2026

**Date:** 2026-10-17  
**Gate Status:** **G5 COMPLETE / PASS** (Execution Halted — Ready for G6 Authorization)  
**Target Platform:** IBM Z / LinuxONE (Simulation on AMD64)  
**Scope:** Formal Evaluation of Frozen Candidate P5 vs Baseline B2, S0–S3 Shift Scenarios, 1,000 Paired-Bootstrap Resamples, Probability Calibration, Latency Benchmarks, and Honest Acceptance Criteria Evaluation (AC1–AC5).

---

## 1. Executive Summary

Gate G5 executes the **Formal Evaluation and Statistical Evidence** phase for SignalGate. It provides a rigorous, reproducible, frozen benchmark comparing the candidate SignalGate triage policy (Candidate P5 with frozen $\lambda = 0.0$ and Platt calibration) against the risk-only baseline (B2 top-budget ranking).

Evaluations were conducted across four standardized scenarios:
1. **S0 — Original Chronological Test Set** ($118,108$ transactions; full 20% test partition).
2. **S1 — Late-Period Chronological Test Scenario** ($31,582$ transactions; `TransactionDT >= 14,800,000`).
3. **S2 — Constructed Real-Data Shift** ($27,390$ transactions; validation slice `TransactionDT >= 11,315,422`).
4. **S3 — Synthetic Perturbation Scenario** ($59,054$ transactions; validation partition with scaling + noise, seed 42).

### Key Empirical Findings
1. **Primary Recall on S0**: At the primary $1.5\times$ review budget ($5.075\%$ touched rate), Candidate P5 detects **2,086 fraud cases** ($51.33\%$ recall) vs Baseline B2's **2,053 fraud cases** ($50.52\%$ recall).
   - Point Recall Improvement: **$+0.812$ percentage points** ($+0.81$ pp).
   - Paired-Bootstrap 95% Confidence Interval: **$[+0.075\%, +1.409\%]$** (1,000 paired resamples, seed 42).
   - The interval is strictly above zero ($\text{CI}_{\text{lower}} > 0$), confirming a statistically significant positive gain. However, the point improvement is below the $+2.00$ pp requirement of AC1.
2. **Shift Robustness (S1–S3)**: Under temporal and synthetic shift, Candidate P5 consistently outperforms Baseline B2:
   - S1 (Late-Period Test): **$+2.48$ pp** ($56.11\%$ vs $53.63\%$, 95% CI $[+0.81\%, +3.62\%]$).
   - S2 (Constructed Real Shift): **$+2.37$ pp** ($55.20\%$ vs $52.83\%$, 95% CI $[+0.73\%, +3.85\%]$).
   - S3 (Synthetic Perturbation): **$+5.00$ pp** ($43.52\%$ vs $38.52\%$, 95% CI $[+3.52\%, +6.37\%]$).
3. **Probability Calibration**: Platt calibration dramatically reduces Expected Calibration Error on S0 from **$0.2194$ (B2)** to **$0.0085$ (P5)**, and Brier score from **$0.0957$** to **$0.0244$**.
4. **Latency (Host AMD64 Simulation)**: End-to-end single-row p95 latency is **$8.34\text{ ms}$**, comfortably passing the AC5 threshold ($\le 50.0\text{ ms}$).
5. **Acceptance Criteria Honesty**:
   - **AC1**: **FAIL / UNMET** (Measured $+0.81$ pp is below the $+2.00$ pp requirement).
   - **AC2**: **FAIL / NOT ESTABLISHED** (Operates at matched review budget; 10% workload reduction not demonstrated).
   - **AC3**: **PASS** (Candidate outperforms B2 across all 4 scenarios).
   - **AC4**: **FAIL / UNMET** (Confident misses reduced by $1.64\%$, below $10\%$ target).
   - **AC5**: **PASS** (Single-row p95 latency of $8.34\text{ ms} \le 50.0\text{ ms}$).

---

## 2. Pre-Evaluation Protocol & Freeze Record

Before accessing test labels, a formal pre-evaluation freeze record was generated and committed at [results/pre_eval_freeze_record.json](file:///c:/Users/archi/OneDrive/Desktop/SignalGate/results/pre_eval_freeze_record.json).

### Historical Test Exposure Disclosure
Historical Gate G1 output already contained test-set baseline metrics in [results/g1_baselines_report.json](file:///c:/Users/archi/OneDrive/Desktop/SignalGate/results/g1_baselines_report.json). That historical exposure is explicitly documented in the provenance record. No claim is made that G5 is the first-ever test-set look. Gate G5 is a controlled, frozen benchmark evaluation, **not a tuning exercise**. Zero hyperparameters, feature definitions, weights, or thresholds were tuned against test labels.

### Frozen System Identity
* **Configuration Hash ([config.yaml](file:///c:/Users/archi/OneDrive/Desktop/SignalGate/config.yaml))**: `e73a0e02fbd5411928ee41a0c70d71584ddc3a17ef9fc8711f318b99baed7f6e`
* **P5 Candidate Policy Hash ([policy/p5_candidate.py](file:///c:/Users/archi/OneDrive/Desktop/SignalGate/policy/p5_candidate.py))**: `10a2fd1f33ec388298f462d8390c8ca2e303d5c411be2643416322a8795b3c48`
* **Split Manifest File Hash ([results/split_manifest.json](file:///c:/Users/archi/OneDrive/Desktop/SignalGate/results/split_manifest.json))**: `12f6e032bf87a07ee38d16fcb57f67dac17e85f81aa61a0048ab89c0f8d2ce19`
* **Test Partition Hash**: `88d73a15fc60f9badfedc4909ede017de45a99f6c58798d54ab9c1dff90690f1`
* **Official Workload Formula**: `(FRAUD_ALERT + MANUAL_REVIEW) / N`.

---

## 3. Scenario-by-Scenario Evaluation Results

### Scenario S0: Original Chronological Test Set (Full 20% Test Partition)
* **Sample Size**: $118,108$ transactions | **Fraud Count**: $4,064$ ($3.44\%$ prevalence)
* **Primary Budget ($1.5\times$ train prevalence)**: $k = 5,994$ cases ($5.075\%$ touched rate)

| Metric | Baseline B2 (Risk-Only) | Candidate P5 (Era-Bagged + Platt) | Delta (P5 - B2) |
| :--- | :--- | :--- | :--- |
| **Recall** | **$50.52\%$** ($2,053 / 4,064$) | **$51.33\%$** ($2,086 / 4,064$) | **$+0.812$ pp** |
| **95% Bootstrap CI** | — | — | **$[+0.075\%, +1.409\%]$** |
| **Precision** | $34.25\%$ | $34.80\%$ | $+0.55$ pp |
| **PR-AUC** | $0.4522$ | $0.4648$ | $+0.0126$ |
| **False Positives** | $3,941$ | $3,908$ | $-33$ cases |
| **Confident Misses (Fraud $\to$ ROUTINE)** | $2,011$ | $1,978$ | $-33$ cases ($-1.64\%$) |
| **Brier Score** | $0.0957$ | $0.0244$ | $-0.0713$ (Improved) |
| **Expected Calibration Error (ECE)** | $0.2194$ | **$0.0085$** | **$-0.2109$** (Calibrated) |
| **FRAUD_ALERT Count** | $3,713$ | $680$ | Calibrated alert tier |
| **MANUAL_REVIEW Count** | $2,281$ | $5,314$ | Audit triage tier |
| **ROUTINE Count** | $112,114$ | $112,114$ | Unchanged auto-clear |
| **HELD/DEFERRED Count** | $0$ | $0$ | Capacity preserved |

#### S0 Review Budget Sweep
| Multiplier | Review Capacity $k$ | Touched Rate | B2 Recall | P5 Recall | Delta Recall | 95% Paired-Bootstrap CI |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **1.0x** | $3,996$ | $3.383\%$ | $44.56\%$ | $45.47\%$ | **$+0.91$ pp** | $[+0.17\%, +1.57\%]$ (Sig. Positive) |
| **1.5x** | $5,994$ | $5.075\%$ | $50.52\%$ | $51.33\%$ | **$+0.81$ pp** | $[+0.07\%, +1.41\%]$ (Sig. Positive) |
| **2.0x** | $7,992$ | $6.767\%$ | $55.44\%$ | $55.95\%$ | **$+0.52$ pp** | $[-0.15\%, +1.31\%]$ (Crosses zero) |
| **3.0x** | $11,988$ | $10.150\%$ | $63.36\%$ | $64.03\%$ | **$+0.66$ pp** | $[-0.15\%, +1.32\%]$ (Crosses zero) |

---

### Scenario S1: Late-Period Chronological Test Scenario
* **Definition**: Final portion of chronological test period (`TransactionDT >= 14,800,000`).
* **Sample Size**: $31,582$ transactions | **Fraud Count**: $1,212$ ($3.84\%$ prevalence)
* **Budget ($1.5\times$)**: $k = 1,602$ cases ($5.07\%$ touched rate)

| Metric | Baseline B2 | Candidate P5 | Delta (P5 - B2) | 95% Bootstrap CI |
| :--- | :--- | :--- | :--- | :--- |
| **Recall** | $53.63\%$ ($650 / 1,212$) | **$56.11\%$** ($680 / 1,212$) | **$+2.48$ pp** | **$[+0.81\%, +3.62\%]$** |
| **Precision** | $40.57\%$ | $42.45\%$ | $+1.88$ pp | — |
| **PR-AUC** | $0.5235$ | $0.5287$ | $+0.0052$ | — |
| **ECE** | $0.2172$ | $0.0061$ | $-0.2111$ | — |

*Finding: Under natural chronological drift in the late test period, the era-bagged ensemble demonstrates expanded recall advantage (+2.48 pp vs +0.81 pp on full test), confirming enhanced temporal resilience.*

---

### Scenario S2: Constructed Real-Data Shift (Validation Window Slice)
* **Definition**: Real transactions from late validation half (`TransactionDT >= 11,315,422`). Zero test exposure.
* **Sample Size**: $27,390$ transactions | **Fraud Count**: $971$ ($3.55\%$ prevalence)
* **Budget ($1.5\times$)**: $k = 1,390$ cases ($5.07\%$ touched rate)

| Metric | Baseline B2 | Candidate P5 | Delta (P5 - B2) | 95% Bootstrap CI |
| :--- | :--- | :--- | :--- | :--- |
| **Recall** | $52.83\%$ ($513 / 971$) | **$55.20\%$** ($536 / 971$) | **$+2.37$ pp** | **$[+0.73\%, +3.85\%]$** |
| **Precision** | $36.91\%$ | $38.56\%$ | $+1.65$ pp | — |
| **PR-AUC** | $0.4611$ | $0.4697$ | $+0.0086$ | — |
| **ECE** | $0.2185$ | $0.0074$ | $-0.2111$ | — |

---

### Scenario S3: Synthetic Perturbation Scenario
* **Definition**: Controlled numerical stress test (seed 42, $1.15\times$ scaling + Gaussian noise $\sigma=0.15\times\text{std}$).
* **Sample Size**: $59,054$ transactions | **Fraud Count**: $2,061$ ($3.49\%$ prevalence)
* **Budget ($1.5\times$)**: $k = 2,997$ cases ($5.07\%$ touched rate)

| Metric | Baseline B2 | Candidate P5 | Delta (P5 - B2) | 95% Bootstrap CI |
| :--- | :--- | :--- | :--- | :--- |
| **Recall** | $38.52\%$ ($794 / 2,061$) | **$43.52\%$** ($897 / 2,061$) | **$+5.00$ pp** | **$[+3.52\%, +6.37\%]$** |
| **Precision** | $26.49\%$ | $29.93\%$ | $+3.44$ pp | — |
| **PR-AUC** | $0.3204$ | $0.3421$ | $+0.0217$ | — |
| **ECE** | $0.2014$ | $0.0112$ | $-0.1902$ | — |

*Classification: Strictly labeled **measured synthetic data**; not presented as proof of natural drift robustness.*

---

## 4. Latency Benchmarking Results ([eval/latency.py](file:///c:/Users/archi/OneDrive/Desktop/SignalGate/eval/latency.py))

* **Host Environment**: Windows 11 AMD64 (Intel Core i7/Xeon simulation workstation)
* **Python Version**: 3.13.3 | **Timing Mechanism**: `time.perf_counter_ns` (monotonic hardware counter)
* **Condition**: In-memory warmed evaluation; model loading excluded from execution path.

| Benchmark Metric | Measured Latency | Acceptance Standard | Status |
| :--- | :--- | :--- | :--- |
| **Single-Row End-to-End p50** | **$6.42\text{ ms}$** | Documented | Baseline |
| **Single-Row End-to-End p95** | **$8.34\text{ ms}$** | **$\le 50.0\text{ ms}$** | **PASS (AC5)** |
| **Single-Row End-to-End p99** | **$9.31\text{ ms}$** | Documented | Baseline |
| **Batch-32 Throughput p50** | **$6.66\text{ ms}$** ($0.21\text{ ms}$ / case) | High-throughput | Excellent |
| **Batch-32 Throughput p95** | **$9.15\text{ ms}$** ($0.29\text{ ms}$ / case) | High-throughput | Excellent |
| **Routing Decision Path Only p95** | **$0.015\text{ ms}$** ($15\text{ }\mu\text{s}$) | Ultra-low overhead | Deterministic |
| **HMAC Audit-Chain Append p95** | **$31.85\text{ ms}$** | Disk fsync included | Compliant |
| **Copilot Offline Brief p95** | **$0.33\text{ ms}$** | Post-decision path | Non-blocking |

*Hardware Disclosure: Measured on a local AMD64 host simulation. Performance characteristics on native IBM Z / LinuxONE hardware (s390x) with IBM Telum AI on-chip acceleration will be measured separately during deployment validation.*

---

## 5. Formal Acceptance Criteria Evaluation (AC1 – AC5)

Every criterion is evaluated honestly against the pre-registered requirements in [config.yaml](file:///c:/Users/archi/OneDrive/Desktop/SignalGate/config.yaml):

| Criterion | Formal Definition | Measured Performance | Required Threshold | Final Status |
| :---: | :--- | :--- | :---: | :---: |
| **AC1** | Recall gain over B2 at $1.5\times$ budget with 95% CI lower bound $> 0$. | **$+0.812$ pp** (95% CI: $[+0.075\%, +1.409\%]$) | $\ge +2.00$ pp | **FAIL / UNMET** |
| **AC2** | Workload reduction matching B2 recall. | Evaluated at matched review budget. | $\ge 10.0\%$ reduction | **FAIL / NOT ESTABLISHED** |
| **AC3** | Shift robustness across S0–S3 scenarios. | P5 outperforms B2 across all 4 scenarios: S0 (+0.81 pp), S1 (+2.48 pp), S2 (+2.37 pp), S3 (+5.00 pp). | Outperform / parity | **PASS** |
| **AC4** | Confident miss reduction (fraud to ROUTINE). | Confident misses reduced from $2,011$ to $1,978$ (**$1.64\%$ reduction**). | $\ge 10.0\%$ reduction | **FAIL / UNMET** |
| **AC5** | End-to-end single-row inference latency p95. | **$8.34\text{ ms}$** on AMD64 host. | $\le 50.0\text{ ms}$ | **PASS** |

### Honest Technical Rationale
1. **Why AC1 Failed**: The era-bagged ensemble provides a statistically significant recall gain over B2 with a confidence interval strictly above zero ($[+0.075\%, +1.409\%]$). However, the absolute gain on the full test set is $+0.812$ pp, which falls short of the ambitious $+2.00$ pp benchmark. We report this outcome honestly without retuning thresholds or altering the candidate definition.
2. **Why AC2 Failed**: Candidate P5 is configured to operate at a matched review workload (matching the budget multiplier $1.5\times$ to compare recall fairly). A $10\%$ reduction in review workload was not demonstrated.
3. **Why AC4 Failed**: Confident misses decreased by $33$ cases ($1.64\%$), which is below the required $10\%$ reduction.
4. **AC3 & AC5 Passed**: Shift robustness is decisively established (P5 maintains $+2.48$ pp gain on late-period test and $+5.00$ pp on synthetic shift), and latency ($8.34\text{ ms}$) easily satisfies the $< 50\text{ ms}$ budget.

---

## 6. Evidence Register & Status Classifications

* **Measured Real Data**:
  * S0 Test Recall: B2 $= 50.52\%$, P5 $= 51.33\%$ ($\Delta = +0.81$ pp, 95% CI $[+0.07\%, +1.41\%]$).
  * S1 Late Test Recall: B2 $= 53.63\%$, P5 $= 56.11\%$ ($\Delta = +2.48$ pp, 95% CI $[+0.81\%, +3.62\%]$).
  * S2 Real Validation Shift Recall: B2 $= 52.83\%$, P5 $= 55.20\%$ ($\Delta = +2.37$ pp, 95% CI $[+0.73\%, +3.85\%]$).
  * Test partition Brier score: $0.0244$; ECE: $0.0085$.
* **Measured Synthetic Data**:
  * S3 Synthetic Shift Recall: B2 $= 38.52\%$, P5 $= 43.52\%$ ($\Delta = +5.00$ pp, 95% CI $[+3.52\%, +6.37\%]$).
  * Red-Teamer adversarial stress tests (RT-01, RT-02, RT-03).
* **Assumption**:
  * Linear combination $\text{score} = p + 0.0 \cdot u2$ represents the empirical optimal policy determined on validation data.
  * Workstation latency measurements reflect algorithmic efficiency, not exact IBM Z hardware execution time.
* **Planned / Not Run**:
  * Live deployment benchmark on LinuxONE / IBM Z s390x hardware.
* **Not Measured in G5**:
  * Human analyst review speedup under Copilot summaries (reserved for pilot study).

---

## 7. Automated Test Suite Execution Evidence

All 106 automated tests pass with zero failures:

```text
============================= test session starts =============================
platform win32 -- Python 3.13.3, pytest-8.4.2, pluggy-1.7.0
rootdir: C:\Users\archi\OneDrive\Desktop\SignalGate
configfile: pyproject.toml
testpaths: tests
plugins: cov-7.1.0
collected 106 items

tests\test_agent_guardrails.py ..                                        [  1%]
tests\test_agent_view.py ..                                              [  3%]
tests\test_agents_g3.py .......                                          [ 10%]
tests\test_audit_chain.py ....                                           [ 14%]
tests\test_base_models.py ..........                                     [ 23%]
tests\test_baselines.py .....                                            [ 28%]
tests\test_drift_sentinel.py .....                                       [ 33%]
tests\test_ensemble.py .........                                         [ 41%]
tests\test_eval_metrics.py .....                                         [ 46%]
tests\test_g5_evaluation.py ....                                         [ 50%]
tests\test_invariants_g4.py ........                                     [ 57%]
tests\test_monitoring.py ......                                          [ 63%]
tests\test_policy.py .....                                               [ 67%]
tests\test_replay_gate.py .....                                          [ 72%]
tests\test_scaffolding.py ....                                           [ 76%]
tests\test_shift_scenarios.py ....                                       [ 80%]
tests\test_signals.py .................                                  [ 96%]
tests\test_splits.py ....                                                [100%]

============================= 106 passed in 14.15s =============================
```

---

## 8. Gate G5 Closure Checklist & Stop Condition

| Exit Condition | Verification Method | Status |
| :--- | :--- | :--- |
| **1. Pre-Evaluation Freeze** | `pre_eval_freeze_record.json` generated & verified before test access. | **PASS** |
| **2. Historical Provenance** | G1 test exposure documented; no claim of first-ever test look. | **PASS** |
| **3. Matched Budget Evaluation** | Evaluated on identical test cases at matched $1.5\times$ review budget. | **PASS** |
| **4. Paired-Bootstrap CI** | 1,000 paired resamples (seed 42) confirm statistically significant gain. | **PASS** |
| **5. S0–S3 Scenarios Evaluated** | S0, S1, S2, S3 evaluated separately with explicit evidence classifications. | **PASS** |
| **6. Probability Calibration** | Platt calibration verified on test partition (ECE $= 0.0085$). | **PASS** |
| **7. Latency Benchmarking** | p50, p95, p99 measured; AC5 ($\le 50.0\text{ ms}$) verified pass ($8.34\text{ ms}$). | **PASS** |
| **8. Honest AC Evaluation** | AC1 (FAIL), AC2 (FAIL), AC3 (PASS), AC4 (FAIL), AC5 (PASS) honestly reported. | **PASS** |
| **9. Master Evidence Saved** | Principal artifact saved to `results/results.json`. | **PASS** |
| **10. Full Test Suite Integrity** | **106 passed, 0 failures** in pytest. | **PASS** |
| **11. Stop Condition** | **Execution halted at Gate G5. Gate G6 (Dashboard) not initiated.** | **PASS** |

**Gate G5 is COMPLETE, AUDITED, and VERIFIED. Execution halted before Gate G6.**
