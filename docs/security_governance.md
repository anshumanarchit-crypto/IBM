# SignalGate Security and Governance Summary
## Boundary Isolation, Claim Verification, Audit Chains, and Human-in-the-Loop Governance

**Document Version:** 1.0.0  
**Date:** 2026-10-17  
**Gate Status:** Gate G7 Submission Readiness  
**Target Architecture:** IBM Z / LinuxONE Enterprise Architecture (Simulated on AMD64)  

---

## 1. Governance Architecture Overview

SignalGate implements an enterprise multi-tier governance framework designed for regulated banking and payment operations. The architecture strictly separates **deterministic decisioning**, **cryptographic audit logging**, and **advisory LLM decision support**.

```
┌────────────────────────────────────────────────────────────────────────┐
│                        TRANSACTION INGESTION                           │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│              DETERMINISTIC DECISION CORE (CANDIDATE P5)                │
│  - 391 Preprocessed Features (Fitted strictly on Train 0-60%)          │
│  - Era-Bagged Heterogeneous Ensemble (5 Era Members)                  │
│  - Platt Calibrator (Fitted strictly on Calibration 60-70%)           │
│  - Deterministic Triage Routing: FRAUD_ALERT, MANUAL_REVIEW, ROUTINE   │
└───────────────────┬────────────────────────────────┬───────────────────┘
                    │                                │
                    ▼                                ▼
       ┌────────────────────────┐       ┌────────────────────────┐
       │   HMAC AUDIT CHAIN     │       │  AGENTVIEW PROJECTION   │
       │   - Sequential SHA-256 │       │  - Sanitized schema    │
       │   - HMAC-SHA256 Sign   │       │  - Zero raw features   │
       │   - Tamper-evident log │       │  - Zero ground truth   │
       └────────────────────────┘       └───────────┬────────────┘
                                                    │
                                                    ▼
                                        ┌────────────────────────┐
                                        │    AGENT SUPERVISOR    │
                                        │  - Filters ROUTINE     │
                                        │  - Dispatches eligible │
                                        └───────────┬────────────┘
                                                    │
                                                    ▼
                                        ┌────────────────────────┐
                                        │   CLAIM VERIFIER &     │
                                        │      COPILOT           │
                                        │  - Fixed claim schema  │
                                        │  - Verified brief      │
                                        └────────────────────────┘
```

---

## 2. Security Invariants & Guardrails

### A. AgentView Boundary Isolation (`AgentCaseView`)
* **Contract:** [schemas/agent_view.py](file:///c:/Users/archi/OneDrive/Desktop/SignalGate/schemas/agent_view.py)
* **Allowlisted Fields:** Strictly limited to `id`, `p` (calibrated risk), `u` (disagreement), `u2` (secondary disagreement), `n` (sample size), `action` (routing lane), `reason` (triage rule code), and `cfg_hash` (provenance hash).
* **Strict Exclusions:**
  - **Zero Raw Features:** The 391 transaction features (`TransactionAmt`, `card1-6`, `V1-V339`, email domains) are **never** passed to agents.
  - **Zero Ground Truth:** Evaluation labels (`isFraud`) are strictly quarantined and never accessible to agents.
  - **Zero PII:** Raw identifiers and customer data are completely excluded.
* **Supervisor Auto-Gating:** [agents/supervisor.py](file:///c:/Users/archi/OneDrive/Desktop/SignalGate/agents/supervisor.py) deterministically rejects `ROUTINE` cases, ensuring agent calls are only permitted for escalated cases (`FRAUD_ALERT`, `MANUAL_REVIEW`, `HELD`).

### B. Claim Verification Engine & Claim Ledger
* **Claim Verifier:** [agents/claim_verifier.py](file:///c:/Users/archi/OneDrive/Desktop/SignalGate/agents/claim_verifier.py) inspects agent output briefs against the sanitized `AgentCaseView`. Any statement referencing an unverified risk score, unverified disagreement, or unauthorized action is blocked before display.
* **Deterministic Claim Ledger:** [governance/claim_ledger.py](file:///c:/Users/archi/OneDrive/Desktop/SignalGate/governance/claim_ledger.py) validates all reported headline numbers against immutable evaluation artifacts ([results/results.json](file:///c:/Users/archi/OneDrive/Desktop/SignalGate/results/results.json)).
  - Requires explicit scenario ID, sample size, and configuration hash.
  - Rejects planted incorrect numbers, mismatched cohort sizes, and fabricated metrics.
  - Employs strict evidence classification: `measured real data`, `measured synthetic data`, `assumption`, `planned work`, `unavailable evidence`, `inconclusive findings`.

### C. HMAC-Authenticated Cryptographic Audit Chain
* **Module:** [governance/audit_chain.py](file:///c:/Users/archi/OneDrive/Desktop/SignalGate/governance/audit_chain.py)
* **Structure:** Each decision record is linked via `prev_hash` and signed with HMAC-SHA256:
  $$\text{record\_hash}_i = \text{SHA256}(\text{payload}_i \parallel \text{prev\_hash}_{i-1} \parallel \text{seq}_i)$$
  $$\text{signature}_i = \text{HMAC-SHA256}(K, \text{record\_hash}_i)$$
* **Tamper Evidence:** Any modification, deletion, or reordering of records breaks the cryptographic chain and is caught immediately by `verify_chain()`.
* **Key Management:** HMAC signing secrets are retrieved from the environment (`SIGNALGATE_AUDIT_HMAC_KEY`). Zero private keys or production secrets are stored in code, configuration, or committed files.

### D. Advisory Drift Sentinel & Human-in-the-Loop Replay Gate
* **Advisory Role:** [agents/drift_sentinel.py](file:///c:/Users/archi/OneDrive/Desktop/SignalGate/agents/drift_sentinel.py) analyzes batch drift diagnostics (PSI, KS). It is strictly advisory and **cannot** directly mutate `config.yaml`, routing thresholds, or model weights.
* **Allowlisted Proposal Keys:** Proposals are restricted to pre-registered configuration parameters (`budget.primary_multiple`, `budget.sweep_multiples`, `thresholds`).
* **Replay Gate & Human Authorization:** [governance/replay_gate.py](file:///c:/Users/archi/OneDrive/Desktop/SignalGate/governance/replay_gate.py) replays any proposed configuration change against held-out validation data (`val_df`), verifying that base hashes match and performance does not degrade before requiring formal Human-in-the-Loop (HIL) sign-off.

---

## 3. Hardware Attestation Disclosures

> [!IMPORTANT]
> **Integrity Disclosure:** All benchmark evaluations, agent executions, and dashboard demonstrations were conducted in standard user space on an AMD64 host simulation.
> 
> **No claim is made** that IBM Secure Execution, confidential computing, or an attested Trusted Execution Environment (TEE) has been demonstrated. Production deployment on IBM Z would require native hardware attestation via IBM Secure Execution for Linux, which is outside the scope of this simulation.

---

## 4. Agent Acceptance Criteria Verification

| Criterion | Requirement / Rule | Verification Method | Status |
| :--- | :--- | :--- | :---: |
| **AG1** | Seeded false claim block rate $= 100\%$ | Evaluated in `test_claim_verifier.py` & `test_claim_ledger.py` | **PASS** |
| **AG2** | Honest brief false block rate $\le 5\%$ | Evaluated across 48 cached agent briefs | **PASS** ($0.0\%$) |
| **AG3** | Audit chain verifies & detects tampering | Tested in `test_audit_chain.py` (bit flip, reorder) | **PASS** |
| **AG4** | Routing byte-identical if agents disabled | Tested in `test_invariants_g4.py` (zero routing dependency) | **PASS** |
| **AG5** | Test label access fails closed | AST boundary analysis in `test_agent_guardrails.py` | **PASS** |
