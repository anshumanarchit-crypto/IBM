# SignalGate Model and Policy Card: Shift-Aware Fraud Triage
## Candidate Policy P5 & Era-Bagged Heterogeneous Ensemble

**System Name:** SignalGate  
**Artifact / Policy Version:** Candidate P5 (`v0.1.0-frozen`)  
**Date:** 2026-10-17  
**Governance Status:** Frozen & Evaluated (Gate G5 / G6 / G7)  
**Target Environment:** IBM Z / LinuxONE Enterprise Architecture (Simulated on AMD64)  
**License:** Apache-2.0  

---

## 1. Intended Use and Domain Scope

### Intended Use
SignalGate is an analytical decision-support and queue-prioritization simulation for enterprise card fraud operations. It is designed to evaluate:
1. Resilient fraud recall under natural chronological distribution shift.
2. Probability calibration to ensure score interpretability.
3. Queue tiering across four operational lanes (`FRAUD_ALERT`, `MANUAL_REVIEW`, `ROUTINE`, `HELD/DEFERRED`).
4. Cryptographic provenance and LLM-assisted decision support under strict boundary isolation.

### Out-of-Scope & Non-Intended Uses
* **NOT a Live Payment Gateway:** SignalGate is not deployed in an active payment processing switch and does not execute real-time transaction blocking.
* **NOT Autonomous Account Closure:** Triage actions generate prioritized analyst review queues; they do not autonomously cancel customer accounts.
* **NOT Proof of TEE Attestation:** Execution is demonstrated in user space; no claim is made of attested IBM Secure Execution.

---

## 2. Model & Ensemble Architecture

### Base Models & Preprocessing
* **Feature Pipeline:** 391 features total (377 numerical features with median imputation, 14 ordinal categorical features with unknown category handling). Preprocessing pipelines are fitted **strictly** on the training partition ($0\text{–}60\%$).
* **Base Estimators:** `HistGradientBoostingClassifier` with max iterations $= 60$ and balanced class weighting.
* **Ensemble Architecture:** `EraBaggedHeterogeneousEnsemble` utilizing 5 chronological era members (omitting eras $0, 1, 2, 3, 4$ sequentially across the training timeline).
* **Calibration Method:** `PlattCalibrator` (univariate sigmoid logistic regression) fitted **strictly** on the calibration partition ($60\text{–}70\%$). Calibration reduces Expected Calibration Error (ECE) from $0.2194$ (uncalibrated) to **$0.0085$** on the test partition.

### Scoring Rule & Candidate P5 Triage Policy
* **Candidate Scoring Formula:**
  $$\text{score}(x) = p(x) + \lambda \cdot u_2(x)$$
  where $p(x)$ is the Platt-calibrated fraud probability, $u_2(x)$ is the secondary ensemble disagreement signal, and $\lambda = 0.0$ is the frozen policy weight.
* **Primary Review Capacity ($1.5\times$):** Budget multiple $1.5\times$ training-set fraud prevalence ($3.38\%$), yielding an investigation capacity budget of $k = 5,994$ cases ($5.075\%$ touched rate) on the $118,108$-row test set.
* **Operational Lanes:**
  - `FRAUD_ALERT` ($p \ge 0.70$): Immediate high-risk alert.
  - `MANUAL_REVIEW` ($p \ge 0.35$ or budget fill): Human fraud analyst queue.
  - `ROUTINE` ($p < 0.35$ and outside budget): Automated clearance.
  - `HELD/DEFERRED`: Queue overflow or capacity hold (0 cases in standard test set).

---

## 3. Training & Evaluation Data

* **Dataset:** IEEE-CIS Fraud Detection Benchmark ($590,540$ labeled transactions).
* **Partitioning Scheme (Chronological by `TransactionDT`):**
  - **Train:** Rows $0\text{–}354,324$ ($60.0\%$, $12,700$ fraud, $3.58\%$ prevalence).
  - **Calibration:** Rows $354,325\text{–}413,378$ ($10.0\%$, $1,999$ fraud, $3.39\%$ prevalence).
  - **Validation:** Rows $413,379\text{–}472,432$ ($10.0\%$, $2,061$ fraud, $3.49\%$ prevalence).
  - **Test (S0):** Rows $472,433\text{–}590,540$ ($20.0\%$, $4,064$ fraud, $3.44\%$ prevalence).
* **Historical Exposure Disclosure:** Historical Gate G1 artifacts evaluated baseline metrics on the test partition. Gate G5 and G6 were conducted as a frozen benchmark evaluation. Zero hyperparameters, weights, or thresholds were tuned against test data.

---

## 4. Benchmark Performance & Statistical Evidence

### Summary Across Shift Scenarios (Matched $1.5\times$ Review Budget)

| Scenario | Cohort Description | Sample Size ($N$) | Fraud Count | Baseline B2 Recall | SignalGate P5 Recall | Delta Recall (P5 - B2) | 95% Bootstrap CI | Evidence Type |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| **S0** | Full Chronological Test Set | $118,108$ | $4,064$ | $50.52\%$ | **$51.33\%$** | **$+0.812$ pp** | $[+0.075\%, +1.409\%]$ | Measured Real Data |
| **S1** | Late-Period Test Scenario | $31,582$ | $1,212$ | $53.63\%$ | **$56.11\%$** | **$+2.48$ pp** | $[+0.81\%, +3.62\%]$ | Measured Real Data |
| **S2** | Real-Data Validation Shift | $27,390$ | $971$ | $52.83\%$ | **$55.20\%$** | **$+2.37$ pp** | $[+0.73\%, +3.85\%]$ | Measured Real Data |
| **S3** | Synthetic Perturbation Stress | $59,054$ | $2,061$ | $38.52\%$ | **$43.52\%$** | **$+5.00$ pp** | $[+3.52\%, +6.37\%]$ | Measured Synthetic Data |

* **S2 Cohort Provenance:** The authoritative count for S2 is **$27,390$ transactions** (`TransactionDT >= 11,315,422`), resolving the theoretical uniform estimate of $29,527$ noted in G4.
* **S3 Scope Disclosure:** S3 applies deterministic Gaussian noise ($\sigma = 0.15 \times \text{std}$) and $1.15\times$ scaling. It tests numerical resilience under covariate noise, but is not presented as proof of natural distribution shift robustness.

---

## 5. Formal Acceptance Criteria Status

| Criterion | Rule / Requirement | Measured Metric | Verified Status | Rationale |
| :--- | :--- | :--- | :---: | :--- |
| **AC1** | Point Recall Gain $\ge +2.00$ pp on S0 | $+0.812$ pp ($95\%\text{ CI: }[+0.075\%, +1.409\%]$) | **FAIL / UNMET** | Significant positive gain ($\text{CI}_{\text{lower}} > 0$), but fails $+2.00$ pp threshold. |
| **AC2** | Touched Rate Workload Reduction $\ge 10\%$ | Matched review budget ($5.075\%$) | **FAIL / NOT ESTABLISHED** | Candidate evaluated at matched budget; 10% reduction not claimed. |
| **AC3** | Outperforms Baseline B2 across S0–S3 | Positive delta across all 4 scenarios | **PASS** | S0: $+0.81$ pp, S1: $+2.48$ pp, S2: $+2.37$ pp, S3: $+5.00$ pp. |
| **AC4** | Confident Miss Reduction $\ge 10\%$ | $1.64\%$ reduction ($2,011 \to 1,978$ misses) | **FAIL / UNMET** | Reduction of $33$ fraud cases is below the $10\%$ target. |
| **AC5** | Single-Row p95 Latency $\le 50.0\text{ ms}$ | Host AMD64 p95 latency $= 8.34\text{ ms}$ | **PASS** | Meets latency bound comfortably on simulation host. |

---

## 6. Operational Lanes & Workload Accounting

Recomputed directly from immutable decision records in [results/results.json](file:///c:/Users/archi/OneDrive/Desktop/SignalGate/results/results.json):

* **Scenario S0 (Full Test, $N=118,108$):**
  - `FRAUD_ALERT`: $680$ transactions ($11.35\%$ of reviewed, $0.58\%$ of total)
  - `MANUAL_REVIEW`: $5,314$ transactions ($88.65\%$ of reviewed, $4.50\%$ of total)
  - `ROUTINE`: $112,114$ transactions ($94.92\%$ of total)
  - `HELD/DEFERRED`: $0$ transactions
  - **Reviewed Cases:** $680 + 5,314 = 5,994$ (Exact match to budget $k=5,994$, $5.075\%$ touched rate)
  - **Total Sum:** $680 + 5,314 + 112,114 + 0 = 118,108$ transactions ($100\%$ consistent)

* **Scenario S1 (Late-Period Test, $N=31,582$):**
  - `FRAUD_ALERT`: $221$ | `MANUAL_REVIEW`: $1,381$ | `ROUTINE`: $29,980$ | `HELD`: $0$
  - **Reviewed Cases:** $221 + 1,381 = 1,602$ (Exact match to budget $k=1,602$, $5.073\%$ touched rate)
  - **Total Sum:** $221 + 1,381 + 29,980 + 0 = 31,582$ transactions ($100\%$ consistent)

* **Scenario S2 (Constructed Real Shift, $N=27,390$):**
  - `FRAUD_ALERT`: $111$ | `MANUAL_REVIEW`: $1,279$ | `ROUTINE`: $26,000$ | `HELD`: $0$
  - **Reviewed Cases:** $111 + 1,279 = 1,390$ (Exact match to budget $k=1,390$, $5.075\%$ touched rate)
  - **Total Sum:** $111 + 1,279 + 26,000 + 0 = 27,390$ transactions ($100\%$ consistent)

* **Scenario S3 (Synthetic Perturbation Stress, $N=59,054$):**
  - `FRAUD_ALERT`: $144$ | `MANUAL_REVIEW`: $2,853$ | `ROUTINE`: $56,057$ | `HELD`: $0$
  - **Reviewed Cases:** $144 + 2,853 = 2,997$ (Exact match to budget $k=2,997$, $5.075\%$ touched rate)
  - **Total Sum:** $144 + 2,853 + 56,057 + 0 = 59,054$ transactions ($100\%$ consistent)

---


## 7. Known Limitations & Caveats

1. **Hardware Measurement Condition:** Latency benchmarks ($8.34\text{ ms}$) were measured on an AMD64 workstation with Python 3.13; they do not represent IBM Telum on-chip AI accelerator hardware execution.
2. **AC1 & AC4 Deficits:** Scientific integrity is strictly preserved: under-performance on AC1 ($+0.81$ pp vs $+2.00$ pp) and AC4 ($1.64\%$ vs $10.0\%$) is reported as FAIL.
3. **Disagreement Parameter ($\lambda = 0.0$):** In Gate G2 validation ablations, non-zero $\lambda$ failed to demonstrate statistical separation from $\lambda = 0.0$. Candidate P5 is therefore frozen at $\lambda = 0.0$, operating as an Era-Bagged Heterogeneous Ensemble with Platt calibration.
