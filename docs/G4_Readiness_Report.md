# Gate G4 Readiness & Acceptance Report: Drift Sentinel, Shift Scenarios and Replay Gate
## Shift-Aware Fraud Triage for IBM Z Datathon 2026

**Date:** 2026-10-17  
**Gate Status:** **G4 COMPLETE / PASS** (Execution Halted — Ready for G5 Authorization)  
**Target Platform:** IBM Z / LinuxONE (Simulation on AMD64)  
**Scope:** Batch Drift Monitoring (`monitoring/`), Advisory Drift Sentinel (`agents/drift_sentinel.py`), Deterministic Replay Gate & Human-in-the-Loop Governance (`governance/replay_gate.py`), Pre-Registered Shift Scenarios (S0–S3) (`data/shift_scenarios.py`), Safety Invariant Verification, and Deterministic Red-Teamer (`governance/red_teamer.py`).

---

## 1. Executive Summary

Gate G4 implements the **Drift Sentinel, Shift Scenarios, and Replay Gate** layer for SignalGate. It provides automated statistical distribution shift monitoring, advisory policy adaptation proposals, and deterministic validation replay with non-negotiable **Human-in-the-Loop (HIL)** governance.

Under no circumstances do monitoring jobs or advisory agents alter the active decision core autonomously. Every proposal is subjected to validation replay on permitted development partitions and requires explicit, cryptographically verifiable human sign-off before candidate versioning.

### Core Architectural Invariants Maintained
1. **Decision System Freeze**: The G1 baselines (B1, B2), the G2 era-bagged heterogeneous ensemble, probability calibrators (Platt ECE $= 0.0039$), feature preprocessors, and the deterministic candidate P5 policy with frozen weight $\lambda = 0.0$ are strictly preserved and untouched.
2. **Ground Truth Isolation (`isFraud`)**: Batch monitoring, drift sentinels, scenario filters, and proposal validation replay operate with zero access to ground-truth test labels.
3. **AgentView & AST Guardrail Boundary**: [agents/drift_sentinel.py](file:///c:/Users/archi/OneDrive/Desktop/SignalGate/agents/drift_sentinel.py) complies fully with static AST isolation rules (zero imports of `data`, `eval`, `models`, `pandas`, `numpy`, or `sklearn`, and zero references to forbidden identifiers).
4. **Deterministic Replay Gate**: [governance/replay_gate.py](file:///c:/Users/archi/OneDrive/Desktop/SignalGate/governance/replay_gate.py) enforces schema validation, allowlisted configuration keys, base configuration hash matching, and replay on validation partitions at matched review workloads.
5. **Human-in-the-Loop Governance**: Proposals that pass validation replay enter status `AWAITING_HUMAN_APPROVAL`. They **never** automatically activate or overwrite operational files without explicit human sign-off (`APPROVED_ACTIVE`).
6. **Fail-Closed Resilience**: Monitoring job failures, agent crashes, or LLM provider timeouts fail closed, leaving the primary triage routing outputs 100% byte-identical.
7. **Full Test Suite Integrity**: All 97 automated tests pass with zero failures.

---

## 2. Preserved G1–G3 System & Evidence Status

The empirical findings and acceptance criteria from previous gates remain frozen and preserved:

### Preserved Historical Facts
* **Ensemble Architecture**: The era-bagged heterogeneous ensemble was retained; the seed-only ensemble was dropped under the pre-registered keep/drop rule ($\text{CI}_{\text{lower}} \le 0$).
* **Validation Recall Gain**: Era-bagged candidate achieves $+1.10\%$ pp recall improvement over B2 at the primary $1.5\times$ review budget with a $95\%$ paired-bootstrap CI of $[+0.241\%, +2.031\%]$.
* **P5 Decision Policy**: Operates with frozen $\lambda = 0.0$ because empirical ablation proved that model disagreement adds no incremental predictive gain over ensemble risk ($\Delta\text{Recall} = -0.087\%$, $95\%$ CI $[-0.403\%, +0.237\%]$). Disagreement $u$ and $u_2$ are preserved as explanatory/audit governance signals.
* **Test Quarantine & Historical Provenance**: Historical Gate G1 artifacts already contain test-set baseline metrics. That historical record is preserved; no claim is made that this is the first-ever test evaluation, and no test metrics were used to tune G4 monitoring or replay gates.
* **Acceptance Criteria Status (config.yaml)**:
  * **AC1**: **UNMET** (Measured $+1.10\%$ pp is below the $+2.0\%$ pp requirement).
  * **AC2**: **NOT ESTABLISHED** ($10\%$ touched workload reduction was not demonstrated).
  * **AC3–AC5**: **NOT MEASURED IN G4** (Preserved for formal evaluation gate on IBM Z).
  * **Keep/Drop Rule**: **PASSED / RETAINED** ($\text{CI}_{\text{lower}} > 0$).

---

## 3. Batch Drift Monitoring Architecture ([monitoring/drift.py](file:///c:/Users/archi/OneDrive/Desktop/SignalGate/monitoring/drift.py))

The batch drift monitoring module calculates statistical shift diagnostics over incoming transaction batches against an immutable baseline reference distribution:

### Statistical Diagnostics
1. **Population Stability Index (PSI)**:
   $$\text{PSI} = \sum_{i=1}^{k} (q_i - p_i) \cdot \ln\left(\frac{q_i}{p_i}\right)$$
   * Binned via 10 quantile intervals derived on the reference baseline with Laplace smoothing ($\epsilon = 10^{-4}$).
   * Severity thresholds: $\text{PSI} < 0.10$ (**stable / none**), $0.10 \le \text{PSI} < 0.25$ (**moderate shift**), $\text{PSI} \ge 0.25$ (**significant shift**).
2. **Two-Sample Kolmogorov-Smirnov (KS) Test**:
   * Evaluates maximum empirical CDF divergence $D = \sup_x |F_{\text{ref}}(x) - F_{\text{curr}}(x)|$ and asymptotic $p$-value.
3. **Edge Case Resilience**:
   * Constant features (zero variance) handled without division-by-zero or math domain exceptions.
   * NaNs and non-finite values are filtered out; missingness counts and rates are explicitly audited.
   * Empty batches ($n=0$) safely emit clean reports with `overall_drift_detected=False`.
4. **Distribution Shift Semantic Invariant**:
   * Every emitted `BatchDriftReport` contains an explicit disclaimer:
     > *"Statistical distribution shift indicates a change in feature or score distributions relative to the reference period. It does NOT constitute proof or evidence that fraud prevalence has increased."*
   * Batch diagnostics operate strictly as monitoring signals, never as an unregistered substitute for transaction-level triage routing.

---

## 4. Advisory Drift Sentinel ([agents/drift_sentinel.py](file:///c:/Users/archi/OneDrive/Desktop/SignalGate/agents/drift_sentinel.py))

The Drift Sentinel is an advisory agent operating outside the primary triage execution path:

```
[ Batch Drift Report (monitoring/drift.py) ]
                  │
                  ▼
[ DriftSentinel (agents/drift_sentinel.py) ]
    ├── No drift detected           --> Returns None (No action)
    ├── External provider timeout   --> Fails closed (Returns None)
    └── Significant drift detected  --> Formulate Advisory Proposal
                  │
                  ▼
[ Typed Proposal (schemas/contracts.py) ]
    ├── Unique proposal_id
    ├── Validated base_cfg_hash
    ├── Allowlisted changes ONLY
    └── Timestamp & rationale
```

### Safety & Guardrail Enforcement
* **AST Isolation**: Pure Python implementation with zero imports of `data`, `eval`, `models`, `pandas`, `numpy`, or `sklearn`, and zero forbidden identifiers (`isFraud`, `y_train`, `y_test`, `test_labels`, `raw_features`, `TransactionAmt`, `TransactionDT`).
* **Allowlisted Configuration Keys Only**:
  Proposals are strictly restricted to:
  * `budget.primary_multiple`
  * `budget.sweep_multiples`
  * `thresholds`
  * `policy.p5.disagreement_weight_lambda`
  * `policy.p5.budget_multiple`
  Attempts to propose changes to unallowlisted keys (e.g. data loaders, training sets, or model architectures) are rejected and fail closed.
* **Offline / Mock Mode**: Operates deterministically without external API dependencies.

---

## 5. Deterministic Replay Gate & Human-in-the-Loop Governance ([governance/replay_gate.py](file:///c:/Users/archi/OneDrive/Desktop/SignalGate/governance/replay_gate.py))

The `ReplayGate` governs all proposals through a 7-step deterministic validation lifecycle:

```
[ Advisory Proposal ]
          │
          ▼
[ Step 1: Validate Schema & Allowlisted Keys ]
          │ (Reject unknown keys or out-of-bounds parameters)
          ▼
[ Step 2: Verify Base Configuration Hash ]
          │ (Must match current frozen core: 10a2fd1f...)
          ▼
[ Step 3: Validation Partition Replay ]
          │ (Replay baseline & candidate on validation data; NO test access)
          ▼
[ Step 4: Verify Workload Constraints & Acceptance Criteria ]
          │ (Touched rate <= max_workload_multiple; Recall not degraded)
          ├── Validation Failed --> Status: REJECTED
          └── Validation Passed --> Status: AWAITING_HUMAN_APPROVAL
                                             │
                                             ▼
                        [ Step 5: Explicit Human Sign-Off ]
                                 (Required: Approver ID & Role)
                                             │
                                             ▼
                                  Status: APPROVED_ACTIVE
```

### Key Replay Invariants
1. **No Autonomous Activation**: Passing validation replay transitions the proposal to `AWAITING_HUMAN_APPROVAL`. It **cannot** become `APPROVED_ACTIVE` without an explicit call to `apply_human_approval(record, approver_id, approver_role)`.
2. **Rejected Proposals Cannot Be Approved**: Attempting to sign off on a rejected proposal immediately raises a `ValueError`.
3. **Cryptographic Audit Provenance**: Emits an immutable `ReplayEvaluationRecord` with SHA-256 provenance checksum hashing all inputs, outputs, and timestamps.
4. **Test Quarantine**: Replay is executed strictly on the permitted validation partition ($59,054$ rows). Held-out test rows and test labels are completely quarantined.

---

## 6. Pre-Registered Shift Scenarios ([data/shift_scenarios.py](file:///c:/Users/archi/OneDrive/Desktop/SignalGate/data/shift_scenarios.py))

Four standardized shift scenarios are defined and recorded in [results/shift_scenarios_manifest.json](file:///c:/Users/archi/OneDrive/Desktop/SignalGate/results/shift_scenarios_manifest.json):

| Scenario ID | Name | Source Partition | Synthetic? | Window / Filter | Row Count | Governance & Data-Use Constraints |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **S0** | **Original Chronological Test Set** | `test` | No | Full 20% test partition (`DT: 12,192,900 – 15,811,131`) | 118,108 | Quarantined benchmark. Historical G1 metrics preserved; strictly no tuning or ranking against it. |
| **S1** | **Late-Period Chronological Scenario** | `test` | No | Pre-registered timestamp filter: `TransactionDT >= 14,800,000` | ~33,000 | Pre-registered long-horizon temporal drift. Defined strictly by time boundary without label inspection. |
| **S2** | **Constructed Real-Data Shift** | `validation` | No | Validation partition slice: `TransactionDT >= 11,315,422` | 29,527 | Real transactions held out from training/calibration. Zero exposure to test partition. |
| **S3** | **Synthetic Perturbation Scenario** | `validation` | Yes | Covariate scaling + Gaussian noise ($\sigma=0.15$), seed=42 | 59,054 | Controlled synthetic stress test. Strictly labeled synthetic, never natural drift. |

*Note: Pre-registering and constructing these scenarios does **NOT** constitute proof that AC3 has passed. Formal AC3 verification belongs to the prescribed evaluation gate.*

---

## 7. Safety Invariant & Red-Teamer Verification

All non-negotiable safety invariants were verified across [tests/test_invariants_g4.py](file:///c:/Users/archi/OneDrive/Desktop/SignalGate/tests/test_invariants_g4.py):

| Invariant | Test ID | Description | Verified Outcome | Status |
| :--- | :--- | :--- | :--- | :--- |
| **High Risk Invariance** | `test_invariant_1` | Highest-risk transactions cannot silently become ROUTINE (auto-cleared). | Highest-risk transaction escalated to review queue. | **PASS** |
| **Fail-Safe Routing** | `test_invariant_2` | Missing or NaN required signals trigger safe escalation (`R0_SIGNAL_UNAVAILABLE` / `MANUAL_REVIEW`). | NaNs routed safely to review queue; audit contracts accept `R0`. | **PASS** |
| **Queue Overflow** | `test_invariant_3` | Capacity exhaustion triggers `R6_QUEUE_CAPACITY` and `HELD`/`DEFERRED` actions. | Verified under AuditRecord contract validation. | **PASS** |
| **Config Immutability** | `test_invariant_4` | Invalid proposals rejected and cannot alter active configuration. | Rejected before replay; zero config mutation. | **PASS** |
| **HIL Enforcement** | `test_invariant_5` | Valid proposals cannot activate without explicit human sign-off. | Remained in `AWAITING_HUMAN_APPROVAL`; never active autonomously. | **PASS** |
| **Routing Invariance** | `test_invariant_6` | Primary routing output remains 100% byte-identical across Sentinel states (disabled, ok, failed, timed_out). | 100% byte-identical decision vectors across all 4 states. | **PASS** |
| **Audit Chain Integrity**| `test_invariant_7` | HMAC authentication, sequence chaining, and tamper detection remain verifiable. | Clean logs verify; single-byte tampering immediately detected. | **PASS** |
| **Red-Teamer Stress** | `test_invariant_8` | Deterministic adversarial stress tests: NaN score injection, score amplification, fabricated claim injection. | Invariants held across all 3 adversarial suites (0 violations). | **PASS** |

---

## 8. Evidence Register & Status Classifications

In accordance with project governance, every finding in Gate G4 is strictly classified:

* **Measured Real Data**:
  * Validation partition baseline recall ($1.5\times$ budget): $70.01\%$.
  * Validation partition candidate P5 recall: $71.11\%$ ($+1.10\%$ pp gain).
  * Platt calibrator ECE on validation: $0.0039$.
  * S2 real-data validation slice row count: $29,527$ transactions.
* **Measured Synthetic Data**:
  * S3 synthetic perturbation scenario (seed 42).
  * Red-Teamer adversarial stress tests (RT-01, RT-02, RT-03).
  * Seeded false claim block rate (AG1: 25/25 rejected).
* **Assumption**:
  * 10 quantile bins with Laplace smoothing ($\epsilon=10^{-4}$) is suitable for continuous feature PSI estimation.
  * Late-period test period (`TransactionDT >= 14,800,000`) captures concept and covariate drift over time.
* **Planned / Not Run**:
  * Deployment and execution on live IBM Z / LinuxONE hardware.
  * Formal AC3 shift robustness benchmark against S1 scenario.
* **Not Measured in G4**:
  * AC3 (Shift robustness $\ge 0.0$).
  * AC4 (Confident miss reduction $\ge 10\%$).
  * AC5 (Inference latency p95 $\le 50\text{ ms}$).
* **Inconclusive**:
  * AC2 (Workload reduction at matched recall) remains unestablished.

---

## 9. Cryptographic Configuration & Artifact Hashes

| Component | File / Path | SHA-256 Checksum |
| :--- | :--- | :--- |
| **Project Configuration** | [config.yaml](file:///c:/Users/archi/OneDrive/Desktop/SignalGate/config.yaml) | `e73a0e02fbd5411928ee41a0c70d71584ddc3a17ef9fc8711f318b99baed7f6e` |
| **P5 Candidate Policy Config** | [policy/p5_candidate.py](file:///c:/Users/archi/OneDrive/Desktop/SignalGate/policy/p5_candidate.py) | `10a2fd1f33ec388298f462d8390c8ca2e303d5c411be2643416322a8795b3c48` |
| **Train Partition Split** | [results/split_manifest.json](file:///c:/Users/archi/OneDrive/Desktop/SignalGate/results/split_manifest.json) | `ee8c38fd7e8b2af1b93a7824fd80f59c7811e5ce2ac1651500d51bf6e2e1f53a` |
| **Calibration Partition Split** | [results/split_manifest.json](file:///c:/Users/archi/OneDrive/Desktop/SignalGate/results/split_manifest.json) | `a1880e4f36558c33d77d0a1a2cf6b1dfe607a4983909364afff71ca84401e7bb` |
| **Validation Partition Split** | [results/split_manifest.json](file:///c:/Users/archi/OneDrive/Desktop/SignalGate/results/split_manifest.json) | `f824d80aea2e20f72e4ed8f06e6d119c7572caf50cf304dfb4224e8d990e7170` |
| **Held-Out Test Partition** | [results/split_manifest.json](file:///c:/Users/archi/OneDrive/Desktop/SignalGate/results/split_manifest.json) | `88d73a15fc60f9badfedc4909ede017de45a99f6c58798d54ab9c1dff90690f1` |
| **Shift Scenarios Manifest** | [results/shift_scenarios_manifest.json](file:///c:/Users/archi/OneDrive/Desktop/SignalGate/results/shift_scenarios_manifest.json) | Generated & verified |

---

## 10. Automated Test Suite Execution Evidence

Command executed:
```powershell
python -m pytest
```

Output:
```text
============================= test session starts =============================
platform win32 -- Python 3.13.3, pytest-8.4.2, pluggy-1.7.0
rootdir: C:\Users\archi\OneDrive\Desktop\SignalGate
configfile: pyproject.toml
plugins: cov-7.1.0
collected 97 items

tests\test_agent_guardrails.py ..                                        [  2%]
tests\test_agent_view.py ..                                              [  4%]
tests\test_agents_g3.py .......                                          [ 11%]
tests\test_audit_chain.py ....                                           [ 15%]
tests\test_base_models.py ..........                                     [ 25%]
tests\test_baselines.py .....                                            [ 30%]
tests\test_drift_sentinel.py .....                                       [ 36%]
tests\test_ensemble.py .........                                         [ 45%]
tests\test_invariants_g4.py ........                                     [ 53%]
tests\test_monitoring.py ......                                          [ 59%]
tests\test_policy.py .....                                               [ 64%]
tests\test_replay_gate.py .....                                          [ 70%]
tests\test_scaffolding.py ....                                           [ 74%]
tests\test_shift_scenarios.py ....                                       [ 78%]
tests\test_signals.py .................                                  [ 95%]
tests\test_splits.py ....                                                [100%]

============================== 97 passed in 12.62s =============================
```

### Complete Test Suite Breakdown
* `tests/test_agent_guardrails.py`: 2 passed (AST isolation guardrails)
* `tests/test_agent_view.py`: 2 passed (schema allowlist)
* `tests/test_agents_g3.py`: 7 passed (AG1–AG5, lifecycle, supervisor)
* `tests/test_audit_chain.py`: 4 passed (HMAC chain integrity and tamper detection)
* `tests/test_base_models.py`: 10 passed (base models, partition guards)
* `tests/test_baselines.py`: 5 passed (B1 & B2 ranking)
* `tests/test_drift_sentinel.py`: 5 passed (proposal creation, allowlisted keys, offline mode, fail-closed)
* `tests/test_ensemble.py`: 9 passed (ensemble mathematics, determinism)
* `tests/test_invariants_g4.py`: 8 passed (routing invariance, HIL approval, fail-safe routing)
* `tests/test_monitoring.py`: 6 passed (PSI, KS, edge cases, DriftMonitor)
* `tests/test_policy.py`: 5 passed (Candidate P5 policy and routing)
* `tests/test_replay_gate.py`: 5 passed (hash mismatch, schema validation, validation replay, HIL sign-off)
* `tests/test_scaffolding.py`: 4 passed (G0 contracts)
* `tests/test_shift_scenarios.py`: 4 passed (S0–S3 scenario specs, builders, manifest export)
* `tests/test_signals.py`: 17 passed (calibrators, ECE, signals)
* `tests/test_splits.py`: 4 passed (chronological boundaries)

**Total: 97 passed, 0 failures.**

---

## 11. Gate G4 Closure Checklist & Stop Condition

| Exit Condition | Verification Method | Status |
| :--- | :--- | :--- |
| **1. Frozen Decision Core** | G1/G2 models, P5 policy, calibrators, and $\lambda=0.0$ untouched. | **PASS** |
| **2. Batch Drift Monitoring** | `monitoring/drift.py` provides deterministic PSI and KS diagnostics. | **PASS** |
| **3. Distribution Shift Disclaimer** | Explicitly distinguishes shift from proof of increased fraud. | **PASS** |
| **4. Advisory Drift Sentinel** | Emits typed `Proposal` records with allowlisted keys; AST compliant. | **PASS** |
| **5. Deterministic Replay Gate** | `governance/replay_gate.py` validates schema, base hash, and capacity. | **PASS** |
| **6. Human-in-the-Loop Governance** | Proposals require explicit human sign-off; cannot auto-activate. | **PASS** |
| **7. Pre-Registered Shift Scenarios** | S0, S1, S2, S3 defined without label access in `data/shift_scenarios.py`. | **PASS** |
| **8. Routing Invariance** | Decisions byte-identical across Sentinel disabled, ok, failed, timed_out. | **PASS** |
| **9. Safety Invariants** | High risk not cleared, NaNs fail safe, overflow triggers R6. | **PASS** |
| **10. Deterministic Red-Teamer** | Adversarial stress tests verify safety invariants hold under perturbation. | **PASS** |
| **11. Test Quarantine** | Test partition ($118,108$ rows) strictly uninspected during G4. | **PASS** |
| **12. Full Test Suite Integrity** | **97 passed, 0 failures** in pytest. | **PASS** |
| **13. Gate Boundary** | Execution halted at Gate G4. Gate G5 (Evaluation Harness) not initiated. | **PASS** |

**Gate G4 is COMPLETE, AUDITED, and VERIFIED. Execution halted before Gate G5.**
