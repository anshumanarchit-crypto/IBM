# SignalGate — Final Plan Compliance Matrix
## IBM Z Datathon 2026 — End-to-End Governance and Audit Register

**Audit Date:** 2026-10-17  
**Auditor / Agent:** Antigravity Autonomous Lead  
**Scope:** Gates G0–G7 Full Plan Compliance, Frozen Artifact Protection, and Reproduction Verification  
**Evaluation Target:** Candidate P5 Policy vs Baseline B2 across Shift Scenarios S0–S3  
**Working Directory:** `C:\Users\archi\OneDrive\Desktop\SignalGate`  

---

## 1. Executive Summary & Verdict

SignalGate has completed formal implementation and verification across Gates G0 through G7 in accordance with the project playbook and competition guidelines.

* **Repository Integrity & Code Health:** **PASS** (123 automated pytest tests passing cleanly with 0 failures, 0 errors, 0 warnings; zero trailing whitespace or formatting defects).
* **Frozen Evidence Protection:** **PASS** (Canonical frozen evaluation artifacts in `results/results.json`, manifests, and pre-evaluation freeze records remain strictly immutable; reproduction outputs are safely isolated in `results/reproduction_run/`).
* **Offline Demonstration Readiness:** **PASS** (Operates entirely offline without external network or API dependencies; verified 9 artifacts, 3 SHA-256 provenance hashes, 4 scenario lane budgets, 20-record HMAC audit chain, and 16 Claim Ledger entries, correctly rejecting a planted false claim).
* **Full Reproduction Fidelity:** **PASS / FULL REPRODUCTION VERIFIED** (Executed `python scripts/reproduce.py --mode full` across all 5 stages in 16m 14s; confirmed 100% exact numerical match across S0–S3 sample sizes, lane budgets, baseline/candidate recalls, and paired bootstrap differences; canonical evidence 100% untouched).
* **Scientific Disclosures & Acceptance Criteria:** Honest, transparent status preserved without modification or tuning (AC1 FAIL, AC2 FAIL, AC3 PASS, AC4 FAIL, AC5 PASS workstation-only).

---

## 2. Gate-by-Gate Plan Compliance Matrix (G0–G7)

| Gate ID & Title | Original Requirement & Objective | Evidence Path / Artifacts | Actual Execution Status | Documented Limitations & Disclosures | Next Action |
| :--- | :--- | :--- | :---: | :--- | :--- |
| **G0: Scaffolding, Schemas & Contracts** | Pure Python architecture, Pydantic contracts (`AuditRecord`, `TriageDecision`, `AgentCaseView`, `ReportableClaim`), deterministic configuration. | [`schemas/contracts.py`](file:///c:/Users/archi/OneDrive/Desktop/SignalGate/schemas/contracts.py)<br>[`schemas/agent_view.py`](file:///c:/Users/archi/OneDrive/Desktop/SignalGate/schemas/agent_view.py)<br>[`config.yaml`](file:///c:/Users/archi/OneDrive/Desktop/SignalGate/config.yaml)<br>[`tests/test_scaffolding.py`](file:///c:/Users/archi/OneDrive/Desktop/SignalGate/tests/test_scaffolding.py) | **PASS** | None. Pure Python and standard scikit-learn stack enforced. | Maintained under Git tracking. |
| **G1: Chronological Splits & Baselines** | Strict temporal 60/10/10/20 train/calibration/validation/test split; FeaturePipeline (391 features); RiskEstimator B1 & B2 evaluation. | [`data/splits.py`](file:///c:/Users/archi/OneDrive/Desktop/SignalGate/data/splits.py)<br>[`models/features.py`](file:///c:/Users/archi/OneDrive/Desktop/SignalGate/models/features.py)<br>[`models/baselines.py`](file:///c:/Users/archi/OneDrive/Desktop/SignalGate/models/baselines.py)<br>[`results/split_manifest.json`](file:///c:/Users/archi/OneDrive/Desktop/SignalGate/results/split_manifest.json)<br>[`results/feature_manifest.json`](file:///c:/Users/archi/OneDrive/Desktop/SignalGate/results/feature_manifest.json)<br>[`results/g1_baselines_report.json`](file:///c:/Users/archi/OneDrive/Desktop/SignalGate/results/g1_baselines_report.json) | **PASS** | **Historical G1 Test Exposure:** Baseline metrics were evaluated on held-out test data in G1 before the formal G5 freeze. Documented across all reports; no models or policies were tuned on test data. | Maintain historical disclosure in model card and audit reports. |
| **G2: Heterogeneous Ensemble & Calibration** | Multi-member ensemble, Platt and Isotonic calibration on calibration split, disagreement signals ($u, u_2$), validation-only selection. | [`models/ensemble.py`](file:///c:/Users/archi/OneDrive/Desktop/SignalGate/models/ensemble.py)<br>[`models/calibration.py`](file:///c:/Users/archi/OneDrive/Desktop/SignalGate/models/calibration.py)<br>[`models/signals/`](file:///c:/Users/archi/OneDrive/Desktop/SignalGate/models/signals)<br>[`results/g2_ensemble_report.json`](file:///c:/Users/archi/OneDrive/Desktop/SignalGate/results/g2_ensemble_report.json)<br>[`results/g2_diversity_report.json`](file:///c:/Users/archi/OneDrive/Desktop/SignalGate/results/g2_diversity_report.json) | **PASS** | Run 1 had a LogisticRegression convergence warning; Run 2 resolved it with train-only StandardScaler and increased iterations (exit code 0). EraBaggedHeterogeneousEnsemble selected for G5. | Preserved as frozen candidate ensemble architecture. |
| **G3: Checked-Claim Agent Layer** | `AgentCaseView` redacting all raw features/labels, deterministic `AgentSupervisor` skipping routine transactions, `ClaimVerifier` catching false claims, `CaseCopilot`. | [`schemas/agent_view.py`](file:///c:/Users/archi/OneDrive/Desktop/SignalGate/schemas/agent_view.py)<br>[`agents/supervisor.py`](file:///c:/Users/archi/OneDrive/Desktop/SignalGate/agents/supervisor.py)<br>[`agents/claim_verifier.py`](file:///c:/Users/archi/OneDrive/Desktop/SignalGate/agents/claim_verifier.py)<br>[`agents/copilot.py`](file:///c:/Users/archi/OneDrive/Desktop/SignalGate/agents/copilot.py)<br>[`tests/test_agents_g3.py`](file:///c:/Users/archi/OneDrive/Desktop/SignalGate/tests/test_agents_g3.py) | **PASS** | Deterministic offline mock LLM provider ensures reproducible offline audit without external network or API dependencies. | Retain deterministic mock provider for competition judging. |
| **G4: Drift Sentinel & Replay Gate** | Shift scenarios S0–S3, `DriftSentinel` with KS/PSI metrics and alert thresholds, deterministic `ReplayGate` with SHA-256 verification. | [`data/shift_scenarios.py`](file:///c:/Users/archi/OneDrive/Desktop/SignalGate/data/shift_scenarios.py)<br>[`monitoring/drift.py`](file:///c:/Users/archi/OneDrive/Desktop/SignalGate/monitoring/drift.py)<br>[`agents/drift_sentinel.py`](file:///c:/Users/archi/OneDrive/Desktop/SignalGate/agents/drift_sentinel.py)<br>[`governance/replay_gate.py`](file:///c:/Users/archi/OneDrive/Desktop/SignalGate/governance/replay_gate.py)<br>[`results/shift_scenarios_manifest.json`](file:///c:/Users/archi/OneDrive/Desktop/SignalGate/results/shift_scenarios_manifest.json)<br>[`results/drift_report.json`](file:///c:/Users/archi/OneDrive/Desktop/SignalGate/results/drift_report.json) | **PASS** | S2 transaction count reconciled to 27,390 rows matching `TransactionDT >= 11,315,422` (29,527 was an unadjusted uniform estimate). | Scenario manifest locked and frozen. |
| **G5: Formal Benchmark & Statistical Evidence** | Pre-evaluation freeze record with SHA-256 hashes; formal evaluation of P5 vs B2 on S0–S3; 1,000 paired bootstrap resamples (seed 42); AC1–AC5 honest evaluation. | [`results/pre_eval_freeze_record.json`](file:///c:/Users/archi/OneDrive/Desktop/SignalGate/results/pre_eval_freeze_record.json)<br>[`results/results.json`](file:///c:/Users/archi/OneDrive/Desktop/SignalGate/results/results.json)<br>[`eval/bootstrap.py`](file:///c:/Users/archi/OneDrive/Desktop/SignalGate/eval/bootstrap.py)<br>[`eval/latency.py`](file:///c:/Users/archi/OneDrive/Desktop/SignalGate/eval/latency.py)<br>[`eval/metrics.py`](file:///c:/Users/archi/OneDrive/Desktop/SignalGate/eval/metrics.py)<br>[`policy/p5_candidate.py`](file:///c:/Users/archi/OneDrive/Desktop/SignalGate/policy/p5_candidate.py)<br>[`docs/G5_Readiness_Report.md`](file:///c:/Users/archi/OneDrive/Desktop/SignalGate/docs/G5_Readiness_Report.md) | **PASS** | **AC1, AC2, AC4 are UNMET / FAIL.** Latency (AC5) measured on local AMD64 workstation, not IBM Z hardware. Zero hardware TEE / IBM Secure Execution attestation. | Maintain strict disclosures; do not tune models to fit criteria. |
| **G6: Claim Ledger & Interactive Dashboard** | Deterministic `ClaimLedger` catching planted claims; Streamlit operational dashboard with offline mode; precomputed agent cache. | [`governance/claim_ledger.py`](file:///c:/Users/archi/OneDrive/Desktop/SignalGate/governance/claim_ledger.py)<br>[`app/streamlit_app.py`](file:///c:/Users/archi/OneDrive/Desktop/SignalGate/app/streamlit_app.py)<br>[`app/dashboard_data.py`](file:///c:/Users/archi/OneDrive/Desktop/SignalGate/app/dashboard_data.py)<br>[`results/agent_cache.json`](file:///c:/Users/archi/OneDrive/Desktop/SignalGate/results/agent_cache.json)<br>[`tests/test_claim_ledger.py`](file:///c:/Users/archi/OneDrive/Desktop/SignalGate/tests/test_claim_ledger.py)<br>[`tests/test_dashboard_g6.py`](file:///c:/Users/archi/OneDrive/Desktop/SignalGate/tests/test_dashboard_g6.py) | **PASS** | S1 clerical typo ($183 / 1,421 \to 1,604$) reconciled with ground-truth artifact ($221 / 1,381 = 1,602$), achieving exact integer match to review budget $k=1,602$. | Dashboard operable offline at port 8501. |
| **G7: Final Reproducibility & Release Packaging** | Dual reproduction entry point (`reproduce.py --mode offline` and `--mode full`); isolated output protection; clean Git tracking; presenter demonstration guide. | [`scripts/reproduce.py`](file:///c:/Users/archi/OneDrive/Desktop/SignalGate/scripts/reproduce.py)<br>[`docs/DEMO_GUIDE.md`](file:///c:/Users/archi/OneDrive/Desktop/SignalGate/docs/DEMO_GUIDE.md)<br>[`docs/FINAL_RELEASE_CHECKLIST.md`](file:///c:/Users/archi/OneDrive/Desktop/SignalGate/docs/FINAL_RELEASE_CHECKLIST.md)<br>[`tests/test_reproduce_isolation.py`](file:///c:/Users/archi/OneDrive/Desktop/SignalGate/tests/test_reproduce_isolation.py) | **PASS** (Offline & Isolation)<br>**PASS** (Full Run Verified) | External presentation slides (`.pptx`) and video file (`.mp4`) are external deliverables not present in the code repository. | Project complete and submission-ready. |


---

## 3. Acceptance Criteria (AC1–AC5) Scientific Audit

The official evaluation results from [`results/results.json`](file:///c:/Users/archi/OneDrive/Desktop/SignalGate/results/results.json) are preserved with 100% scientific honesty:

| Criterion | Target Specification | Baseline B2 Result | Candidate P5 Result | Measured Delta / Point Estimate | 95% Bootstrap CI (Seed 42) | Official Status | Honest Scientific Reasoning |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :--- |
| **AC1** | $\ge +2.00$ pp recall improvement over B2 at 1.5x budget; 95% CI lower bound $> 0$. | 50.52% ($2,053 / 4,064$) | 51.33% ($2,086 / 4,064$) | **$+0.812$ pp** ($+33$ frauds) | $[+0.075\%, +1.409\%]$ | **FAIL / UNMET** | While the recall improvement is statistically significant ($p = 0.015$), the point estimate of $+0.812$ pp falls short of the required $+2.00$ pp threshold. |
| **AC2** | Match B2 recall while touching $\ge 10\%$ fewer transactions. | 5.075% review rate | 5.075% review rate | Matched budget evaluated | — | **FAIL / NOT ESTABLISHED** | Candidate P5 was evaluated under matched-workload parity ($k=5,994$ cases). A separate reduced-budget sweep achieving equal recall with $10\%$ lower volume was not formally established. |
| **AC3** | Shift robustness: outperform Baseline B2 across scenarios S0, S1, S2, and S3. | S0: 50.52%<br>S1: 46.12%<br>S2: 44.90%<br>S3: 38.04% | S0: 51.33%<br>S1: 48.60%<br>S2: 47.27%<br>S3: 43.04% | **S0: $+0.81$ pp**<br>**S1: $+2.48$ pp**<br>**S2: $+2.37$ pp**<br>**S3: $+5.00$ pp** | S0: $[+0.07\%, +1.41\%]$<br>S1: $[+0.83\%, +4.04\%]$<br>S2: $[+0.82\%, +3.91\%]$<br>S3: $[+3.74\%, +6.21\%]$ | **PASS** | Candidate P5 demonstrates superior shift resilience, exceeding Baseline B2 across all 4 evaluation scenarios with positive confidence interval bounds. |
| **AC4** | $\ge 10\%$ reduction in confident misses (fraudulent cases routed to `ROUTINE`). | 2,011 misses | 1,978 misses | **$-1.64\%$** ($-33$ misses) | — | **FAIL / UNMET** | Confident misses were reduced from 2,011 to 1,978 cases, representing a $1.64\%$ relative reduction, well below the required $10.0\%$ target. |
| **AC5** | Single-row inference latency $\le 50.0$ ms (p95). | — | **8.34 ms** (p95)<br>4.21 ms (p50)<br>12.60 ms (p99) | **$-41.66$ ms** under target | — | **PASS** (Workstation Simulation Only) | Measured single-row p95 latency is 8.34 ms on local AMD64 workstation simulation. **IBM Z hardware disclosure:** Not measured on IBM Telum or Linux on IBM Z hardware. |

---

## 4. Cryptographic Provenance & Audit Chains

| Verification Element | Canonical Value / Hash | Verification Target | Status |
| :--- | :--- | :--- | :---: |
| **`config.yaml` SHA-256** | `e73a0e02fbd5411928ee41a0c70d71584ddc3a17ef9fc8711f318b99baed7f6e` | Pre-eval freeze record hash | **MATCH / PASS** |
| **Test Split Partition Hash** | `88d73a15fc60f9badfedc4909ede017de45a99f6c58798d54ab9c1dff90690f1` | Split manifest test hash | **MATCH / PASS** |
| **Candidate P5 Policy Hash** | `10a2fd1f33ec388298f462d8390c8ca2e303d5c411be2643416322a8795b3c48` | P5 configuration fingerprint | **MATCH / PASS** |
| **Split Manifest File SHA-256**| `12f6e032bf87a07ee38d16fcb57f67dac17e85f81aa61a0048ab89c0f8d2ce19` | Canonical manifest file hash | **MATCH / PASS** |
| **HMAC Audit Log Chain** | 20 sequential records, signed with SHA-256 HMAC | `results/sample_audit_chain.jsonl` | **MATCH / PASS** |
| **Claim Ledger Integrity** | 16/16 claims verified; 1 planted adversarial claim caught | `results/results.json` vs Ledger | **MATCH / PASS** |

---

## 5. Demonstration & Presentation Verification

| Demonstration Requirement | Procedure & Reference | Status | Specific Note |
| :--- | :--- | :---: | :--- |
| **Offline Demonstration Command** | `python scripts/reproduce.py --mode offline` | **PASS** | Runs in $< 10$ seconds, zero data/network required, verifies all governance proofs. |
| **Interactive Streamlit Dashboard** | `streamlit run app/streamlit_app.py` | **PASS** | Verified operational on port 8501, displays all 6 pages with audited figures. |
| **5-Minute Demonstration Script** | [`docs/DEMO_GUIDE.md`](file:///c:/Users/archi/OneDrive/Desktop/SignalGate/docs/DEMO_GUIDE.md) | **PASS** | Complete 300-second verbatim script with second-by-second screen guidance. |
| **Rehearsed Twice Proof** | Presenter rehearsal protocol in `DEMO_GUIDE.md` | **PARTIALLY VERIFIED** | The rehearsal protocol and timing checkpoints are documented; actual verbal rehearsal is an interactive human presenter action. |
| **Presentation Slide Deck (`.pptx`)** | Submission rules slide requirement | **NOT PRESENT** | No `.pptx` or `.pdf` slide deck is checked into the git repository. Presenter must generate slides from `results/results.json` if required. |
| **Video Recording File (`.mp4`)** | Competition submission recording | **NOT PRESENT** | Video file is an external upload deliverable. Recording specifications (1080p, OBS, 5-minute cap) are documented in `DEMO_GUIDE.md`. |

---

## 6. Repository Tracking & File Boundary Verification

| Path / File | Tracking Rule | Git Status |
| :--- | :--- | :---: |
| **`README.md`** | Source documentation | Tracked (`git ls-files` PASS) |
| **`scripts/reproduce.py`** | Master reproduction entry point | Tracked (`git ls-files` PASS) |
| **`data/splits.py`** | Chronological splitting implementation | Tracked (`git ls-files` PASS) |
| **`results/results.json`** | Canonical master evaluation evidence | Tracked (`git ls-files` PASS) |
| **`data/raw/*.csv`** | Heavy raw datasets (683 MB) | **Strictly Excluded** (`.gitignore:81:*.csv`) |
| **`.venv/`** | Virtual environment binaries | **Strictly Excluded** (`.gitignore:30:.venv/`) |
| **`results/reproduction_run/`** | Isolated reproduction scratch directory | **Strictly Excluded** (`.gitignore:99:results/reproduction_run/`) |

---

## 7. Compliance Sign-Off

The SignalGate codebase is complete, auditable, and defensively protected against accidental overwriting of canonical evidence. All scientific, governance, and hardware limitations are disclosed with full transparency.
