# SignalGate: Shift-Aware Fraud Triage for IBM Z Datathon 2026

[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![Tests Passing](https://img.shields.io/badge/Tests-120%20Passed-success.svg)](tests/)
[![Architecture](https://img.shields.io/badge/Target-IBM%20Z%20%2F%20LinuxONE-lightgrey.svg)](infra/)
[![Evaluation](https://img.shields.io/badge/Status-Frozen%20Benchmark-informational.svg)](results/results.json)
[![License](https://img.shields.io/badge/License-Apache%202.0-green.svg)](LICENSE)

SignalGate is an enterprise shift-aware fraud triage decision-support simulation engineered for **IBM Z and LinuxONE** enterprise architectures. The system provides resilient fraud detection under temporal and covariate distribution shift by coupling an era-bagged heterogeneous ensemble and Platt probability calibration with deterministic operational triage routing, an HMAC-authenticated cryptographic audit chain, and an advisory LLM decision-support layer.

> [!IMPORTANT]
> **Scope & Governance Notice:** SignalGate is an analytical decision-support and queue-prioritization simulation. It is **not** a live settlement, automated transaction-interruption, or payment-blocking service. All evaluation metrics are precomputed and frozen in [results/results.json](results/results.json). Execution is conducted on an AMD64 host simulation; no claim of attested IBM Secure Execution hardware is made.

---

## 1. Non-Negotiable Architectural Invariants

SignalGate adheres strictly to the following architectural boundaries across all development gates (G0–G7):

1. **Deterministic Execution Core:** All numerical inferences, probability calibrations, and queue-routing decisions are executed via deterministic, reproducible logic.
2. **Quarantined Ground Truth:** The label `isFraud` is strictly an offline benchmark evaluation metric. It is **never** accessible as a feature or routing parameter.
3. **Strict AgentView Boundary:** LLM agents ingest strictly allowlisted `AgentCaseView` projections (`p`, `u`, `u2`, `n`, `action`, `reason`, `cfg_hash`). Raw feature vectors (391 features) and ground truth are **never** accessible to agents.
4. **Frozen Evaluation Integrity:** All models, hyperparameters, and triage thresholds were frozen prior to formal evaluation. Zero test-set tuning was performed.
5. **Advisory Drift Sentinel & HIL Replay:** The Drift Sentinel emits strictly advisory adaptation proposals for allowlisted configuration keys. Proposals require deterministic validation replay and explicit Human-in-the-Loop (HIL) authorization before activation.
6. **Cryptographic Provenance:** Every routing decision is sequentially linked and signed using an HMAC-SHA256 cryptographic audit chain.

---

## 2. Empirical Findings & Headline Results

Evaluated across four standardized scenarios at a matched $1.5\times$ review budget ($5.075\%$ touched rate, $k = 5,994$ cases on test):

| Scenario | Cohort Description | Sample Size ($N$) | Baseline B2 Recall | SignalGate P5 Recall | Delta Recall (P5 - B2) | 95% Bootstrap CI (1,000 resamples) | PR-AUC Gain | ECE Calibration Gain | Evidence Classification |
| :---: | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| **S0** | Full Chronological Test Set | $118,108$ | $50.52\%$ | **$51.33\%$** | **$+0.812$ pp** | **$[+0.075\%, +1.409\%]$** | $+0.0126$ | $-0.2109$ ($0.2194 \to 0.0085$) | Measured Real Data |
| **S1** | Late-Period Test Scenario | $31,582$ | $53.63\%$ | **$56.11\%$** | **$+2.48$ pp** | **$[+0.81\%, +3.62\%]$** | $+0.0052$ | $-0.2111$ ($0.2172 \to 0.0061$) | Measured Real Data |
| **S2** | Real-Data Validation Shift | $27,390$ | $52.83\%$ | **$55.20\%$** | **$+2.37$ pp** | **$[+0.73\%, +3.85\%]$** | $+0.0086$ | $-0.2111$ ($0.2185 \to 0.0074$) | Measured Real Data |
| **S3** | Synthetic Perturbation Stress | $59,054$ | $38.52\%$ | **$43.52\%$** | **$+5.00$ pp** | **$[+3.52\%, +6.37\%]$** | $+0.0217$ | $-0.1902$ ($0.2014 \to 0.0112$) | Measured Synthetic Data |

* **Scenario S2 Reconciliation:** S2 contains **$27,390$ transactions** satisfying `TransactionDT >= 11,315,422`. This authoritative count resolves the preliminary uniform midpoint estimate of $29,527$ noted in G4.
* **Latency Benchmark (Host AMD64):** Single-row p50 $= 6.42\text{ ms}$, p95 $= \mathbf{8.34\text{ ms}}$ (comfortably passing the AC5 requirement of $\le 50.0\text{ ms}$), p99 $= 9.31\text{ ms}$. Batch-32 p95 $= 9.15\text{ ms}$.

---

## 3. Honest Acceptance Criteria Status

In accordance with scientific integrity principles, all criteria are reported with their true status:

| Criterion | Target Requirement | Observed Result | Status | Scientific Finding |
| :---: | :--- | :--- | :---: | :--- |
| **AC1** | S0 Recall Gain $\ge +2.00$ pp | $+0.812$ pp (95% CI $[+0.075\%, +1.409\%]$) | **FAIL / UNMET** | Statistically significant positive improvement ($\text{CI}_{\text{lower}} > 0$), but below $+2.00$ pp target. |
| **AC2** | Touched Rate Workload Reduction $\ge 10\%$ | Evaluated at matched review budget ($5.075\%$) | **FAIL / NOT ESTABLISHED** | Candidate evaluated at matched budget; 10% reduction not claimed. |
| **AC3** | Shift Robustness across S0–S3 | P5 outperforms B2 across all 4 scenarios | **PASS** | Consistent gain: S0 ($+0.81$), S1 ($+2.48$), S2 ($+2.37$), S3 ($+5.00$). |
| **AC4** | Confident Miss Reduction $\ge 10\%$ | $1.64\%$ reduction ($2,011 \to 1,978$ misses) | **FAIL / UNMET** | Modest reduction of $33$ fraud cases; below $10\%$ target. |
| **AC5** | Single-Row p95 Latency $\le 50.0\text{ ms}$ | Host AMD64 p95 latency $= 8.34\text{ ms}$ | **PASS** | Meets latency bound comfortably on simulation workstation. |

---

## 4. Cryptographic Provenance & Verification

The integrity of this benchmark is guaranteed by verifiable cryptographic hashes:
* **Configuration SHA-256 ([config.yaml](config.yaml)):** `e73a0e02fbd5411928ee41a0c70d71584ddc3a17ef9fc8711f318b99baed7f6e`
* **Test Partition Hash ([results/split_manifest.json](results/split_manifest.json)):** `88d73a15fc60f9badfedc4909ede017de45a99f6c58798d54ab9c1dff90690f1`
* **Candidate P5 Policy Hash ([policy/p5_candidate.py](policy/p5_candidate.py)):** `10a2fd1f33ec388298f462d8390c8ca2e303d5c411be2643416322a8795b3c48`
* **Pre-Evaluation Freeze Record:** [results/pre_eval_freeze_record.json](results/pre_eval_freeze_record.json)
* **Master Evaluation Record:** [results/results.json](results/results.json)

---

## 5. Reproduction Workflows

SignalGate provides two distinct, documented workflows:

### Workflow A: Offline Demonstration & Audit (Zero Data Download Required)
Operates purely from immutable saved evaluation artifacts in `results/`. Requires zero training data and zero external network access:

```bash
# 1. Setup virtual environment
python -m venv .venv
# On Windows:
.\.venv\Scripts\Activate.ps1
# On Linux/macOS:
source .venv/bin/activate

# 2. Install dependencies
pip install -r requirements.txt
pip install -r requirements-ml.txt

# 3. Execute master reproducibility audit & Claim Ledger verification
python scripts/reproduce.py --mode offline
# or via Makefile:
make audit

# 4. Launch interactive offline Streamlit dashboard
streamlit run app/streamlit_app.py --server.headless true --server.port 8501
# or via Makefile:
make demo-offline
```

### Workflow B: Full Experiment Reproduction (Requires Dataset)
Retrains the era-bagged ensemble and re-runs the entire benchmark from the labeled IEEE-CIS Fraud Detection dataset:
1. Download `train_transaction.csv` (683 MB) into `data/raw/train_transaction.csv`.
2. Execute the full pipeline:
```bash
python scripts/reproduce.py --mode full
# or via Makefile:
make reproduce-full
```

---

## 6. Repository Layout

```
SignalGate/
├── app/                    # Interactive Streamlit dashboard & data verification helpers
│   ├── streamlit_app.py    # 8-panel governance & triage dashboard
│   └── dashboard_data.py   # Deterministic artifact loader & lane counter verifier
├── agents/                 # Boundary-isolated LLM decision-support agents
│   ├── supervisor.py       # Deterministic dispatcher (filters ROUTINE cases)
│   ├── copilot.py          # Case Copilot generating typed claim briefs
│   ├── claim_verifier.py   # Verification engine validating claims against AgentCaseView
│   └── drift_sentinel.py   # Advisory drift monitoring agent
├── governance/             # Audit chains, Claim Ledger, and HIL Replay Gate
│   ├── audit_chain.py      # HMAC-authenticated sequential audit log writer & verifier
│   ├── claim_ledger.py     # Deterministic claim ledger validating headline metrics
│   ├── replay_gate.py      # Replay Gate for advisory adaptation proposals
│   └── red_teamer.py       # Adversarial invariant stress tester
├── models/                 # Statistical modeling and feature pipelines
│   ├── ensemble.py         # EraBaggedHeterogeneousEnsemble (5 era members)
│   ├── calibration.py      # PlattCalibrator (sigmoid logistic regression)
│   ├── features.py         # 391-feature preprocessing pipeline
│   └── baselines.py        # TopBudgetBaseline (Baseline B2)
├── policy/                 # Triage policy definitions
│   └── p5_candidate.py     # Candidate P5 routing policy (lambda = 0.0)
├── results/                # Immutable frozen evaluation and governance artifacts
│   ├── results.json        # Master evaluation record (S0-S3, latency, criteria)
│   ├── pre_eval_freeze_record.json  # Cryptographic pre-evaluation freeze record
│   ├── agent_cache.json    # Cached sanitized agent outputs and verified briefs
│   ├── drift_report.json   # Saved PSI and KS distribution shift diagnostics
│   └── sample_audit_chain.jsonl     # 20-record HMAC verified audit log
├── scripts/                # Reproduction and evaluation scripts
│   ├── reproduce.py        # Master reproduction entry point (offline & full modes)
│   ├── cache_agent_outputs.py # Permitted agent cache generator
│   └── run_g5_eval.py      # Master G5 formal evaluation pipeline
├── docs/                   # System documentation & readiness reports
│   ├── model_policy_card.md # Model and Policy Card
│   ├── security_governance.md # Security & governance summary
│   ├── DEMO_GUIDE.md       # Presenter script & 1080p recording checklist
│   ├── G1_Readiness_Report.md through G7_Readiness_Report.md
│   └── ML_Evidence_Audit.md # Literature and evidence audit
├── data/                   # Chronological splitting and shift scenario definitions
│   ├── splits.py           # 60/10/10/20 chronological partitioner
│   └── shift_scenarios.py  # S0, S1, S2, S3 scenario generators
└── tests/                  # Automated test suite (120 tests passing)
```

---

## 7. Testing & Verification

Run the complete 120-test automated test suite:
```bash
pytest -q
```
* **Result:** **120 passed in ~6.5 seconds** (0 failures, 0 errors, 0 warnings).

---

## 8. Documentation References

* **[Model and Policy Card](docs/model_policy_card.md):** Complete specifications of model architecture, calibration, evaluation data, workload assumptions, and limitations.
* **[Security and Governance Summary](docs/security_governance.md):** Architectural boundaries, AgentView isolation, Claim Ledger validation, HMAC audit chains, and HIL Replay Gate governance.
* **[Presenter Guide & Screen-Recording Protocol](docs/DEMO_GUIDE.md):** 8-panel presenter script, talking points, and 1080p demonstration recording protocol.
* **[Readiness Reports](docs/):** Comprehensive gate-by-gate audit reports from Gate G1 through Gate G7.
