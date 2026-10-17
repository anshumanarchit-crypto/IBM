# SignalGate Presenter Guide and Demonstration Checklist
## Interactive Governance Dashboard & Screen-Recording Protocol

**Document Version:** 1.0.0  
**Date:** 2026-10-17  
**Gate Status:** Gate G7 Submission Readiness  
**Target Environment:** Local Offline Host (No external APIs or training required)  

---

## 1. Quick Launch Instructions (Offline Demonstration)

The SignalGate demonstration runs completely offline from immutable, precomputed evaluation artifacts:

```bash
# 1. Activate project virtual environment
# On Windows (PowerShell):
.venv\Scripts\activate

# On Linux / macOS (Bash):
source .venv/bin/activate

# 2. Launch Streamlit dashboard
streamlit run app/streamlit_app.py --server.headless true --server.port 8501
```

Once launched, open your web browser to: **`http://localhost:8501`**.

---

## 2. Presenter Script & 8-Panel Walkthrough Checklist

| Panel # | Panel Name | Presenter Talking Points | Key Visual Elements |
| :---: | :--- | :--- | :--- |
| **0** | **Header & Sidebar** | "Notice the top governance banner: this is a benchmark and replay demonstration, not a live payment processing service. In the sidebar, cryptographic SHA-256 hashes for `config.yaml`, the test split, and the candidate policy are verified in real time." | Header disclaimer banner, sidebar green hash badges. |
| **1** | **Executive Comparison** | "Here on the full 118,108-case test set (S0), SignalGate Candidate P5 achieves 51.33% recall vs 50.52% for Baseline B2 at the exact same 1.5× review budget (5.075% touched rate). The paired-bootstrap 95% confidence interval is strictly positive: [+0.075%, +1.409%]. Platt calibration reduces Expected Calibration Error from 0.2194 down to 0.0085." | Metric cards (Recall, Precision, PR-AUC, ECE), comparison table, budget sweep. |
| **2** | **Operational Lanes** | "SignalGate routes transactions into 4 operational lanes: 680 to FRAUD_ALERT, 5,314 to MANUAL_REVIEW, and 112,114 to ROUTINE auto-clearance. The sum of all lanes exactly equals 118,108 cases. In the Confident Misses card, SignalGate reduces false negatives by 1.64% (from 2,011 to 1,978); we honestly disclose that AC4 required 10%, so AC4 is marked FAIL." | Lane counter cards, sum consistency check, confident misses honest disclosure. |
| **3** | **Shift Scenarios (S0–S3)** | "Under natural chronological drift in S1, our recall advantage expands to +2.48 pp. In real validation shift S2, it is +2.37 pp. Notice our authoritative reconciliation: S2 contains exactly 27,390 transactions under the timestamp filter, resolving the uniform estimate of 29,527 from G4. In S3, synthetic perturbation yields +5.00 pp, which is strictly classified as measured synthetic data." | Shift comparison table, reconciliation notes, synthetic scope disclosure. |
| **4** | **Case Drilldown & Briefs** | "Inspect individual transactions. Notice the strict security boundary: agents ingest only allowlisted AgentCaseView fields (calibrated p, disagreement u, action, reason). Raw features and true labels are completely blocked. The Copilot generates verified briefs with typed claim contracts." | Case selector dropdown, JSON AgentCaseView, verified statements, claim contracts. |
| **5** | **Batch Drift Monitoring** | "The Drift Sentinel monitors batch PSI and KS statistics across monitored features. Notice the prominent statistical disclaimer: distribution shift measures covariate change; it does NOT constitute proof of increased fraud." | PSI/KS table, shift severity badges, statistical disclaimer box. |
| **6** | **Claim Ledger & Provenance** | "The Claim Ledger verifies all 16 registered headline claims against frozen artifacts. Now toggle the 'Simulate Planted Incorrect Claim' checkbox: the ledger immediately catches and rejects the fabricated 85% recall claim with an explicit rejection reason. The live HMAC audit chain verifies 20 linked decision records." | 16/16 verified claims table, planted-error adversarial checkbox, HMAC audit chain status. |
| **7** | **Latency Benchmarks** | "Host single-row p95 latency is 8.34 ms, comfortably within the 50 ms budget (AC5 PASS). We disclose that this benchmark reflects our AMD64 simulation workstation, not an on-chip IBM Z Telum coprocessor." | Latency metric cards (p50, p95, p99, batch-32), host hardware disclosure. |
| **8** | **Acceptance Checklist** | "SignalGate upholds complete scientific integrity: AC1 (FAIL / UNMET, +0.81 pp vs +2.00 pp target), AC2 (FAIL / NOT ESTABLISHED), AC3 (PASS, robust across shifts), AC4 (FAIL / UNMET, 1.64% miss reduction vs 10%), AC5 (PASS, 8.34 ms <= 50 ms)." | Formal acceptance criteria checklist table, integrity summary. |

---

## 3. Manual Screen-Recording Protocol (1920×1080)

Follow this protocol to produce a video demonstration for project archiving or submission review:

### Technical Specifications:
* **Resolution:** 1920 × 1080 (1080p, 16:9 aspect ratio)
* **Framerate:** 30 fps or 60 fps
* **Format:** MP4 (H.264 video, AAC audio if narrated)
* **Target Duration:** 2 minutes 30 seconds to 3 minutes 30 seconds

### Recording Execution Sequence:
1. **Pre-Flight (0:00 – 0:10):**
   - Start browser at full 1080p window without browser bookmarks bar or developer tools.
   - Navigate to `http://localhost:8501`.
   - Verify sidebar status displays all three hashes as verified (green badges).
2. **Tab 1: Executive Comparison (0:10 – 0:40):**
   - Hover over the Recall metric card showing `+0.81 pp` and 95% CI `[+0.075%, +1.409%]`.
   - Scroll down through the head-to-head comparison table and budget sweep table.
3. **Tab 2: Operational Lanes (0:40 – 1:00):**
   - Point to the Lane Counter Verification banner showing exact `118,108 / 118,108` sum.
   - Highlight the Confident Misses reduction ($2,011 \to 1,978$) and honest AC4 FAIL disclosure.
4. **Tab 3: Shift Scenarios (1:00 – 1:25):**
   - Review S0, S1, S2, S3 results.
   - Highlight the S2 reconciliation note ($27,390$ actual rows vs $29,527$ uniform estimate).
5. **Tab 4: Case Drilldown (1:25 – 1:50):**
   - Select an escalated case (`FRAUD_ALERT` or `MANUAL_REVIEW`).
   - Show sanitized JSON `AgentCaseView` and verified brief statements.
6. **Tab 5: Drift Monitoring (1:50 – 2:10):**
   - Show PSI/KS values and highlight the disclaimer box (*shift != fraud*).
7. **Tab 6: Claim Ledger (2:10 – 2:40):**
   - Review verified headline claims table ($16/16$ passed).
   - Click "Simulate Planted Incorrect Claim" checkbox to demonstrate adversarial rejection live.
   - Show HMAC audit chain verification status.
8. **Tab 7 & 8: Latency & Acceptance Checklist (2:40 – 3:00):**
   - Show single-row latency ($8.34\text{ ms}$) and AMD64 workstation disclosure.
   - Conclude on the honest AC1–AC5 acceptance criteria checklist.

### Current Recording Status Disclosure:
> [!NOTE]
> **Recording File Status:** An external pre-recorded video file (`.mp4`) is **not currently committed** to the repository to prevent repository bloat. The live dashboard can be launched and recorded at any time following the exact protocol above.

---

## 4. Submission Materials Audit

* **Presentation Deck (`.pptx`, `.pdf`, `.key`):** **None present** in the repository.
* **External Submission Text:** **None present** in the repository.
* **Integrity Audit:** All reported figures, citations, and claims in this repository are derived directly from immutable evaluation artifacts ([results/results.json](file:///c:/Users/archi/OneDrive/Desktop/SignalGate/results/results.json)). No claims of live production deployment, automated payment interruption, or attested IBM Secure Execution exist in any project file.
