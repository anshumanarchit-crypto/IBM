# Gate G3 Readiness & Acceptance Report: Checked-Claim Agent Layer
## Shift-Aware Fraud Triage for IBM Z Datathon 2026

**Date:** 2026-10-17  
**Gate Status:** **G3 COMPLETE / PASS** (Execution Halted — Ready for G4 Authorization)  
**Target Platform:** IBM Z / LinuxONE (Simulation on AMD64)  
**Scope:** AgentView Boundary Enforcement, Deterministic Supervisor, Claim Verifier, Case Copilot, and AG1–AG5 Acceptance Criteria  

---

## 1. Executive Summary

Gate G3 implements the **Checked-Claim Agent Layer** for SignalGate. It establishes strict structural guardrails ensuring that LLM agents operate purely as post-decision audit and explanation support tools.

Under no circumstances do agents influence automated transaction routing, access raw features or ground-truth labels, or display unverified natural language text to fraud analysts.

### Key Architectural Invariants
1. **Decision System Freeze**: G1 and G2 models, preprocessors, calibrators, ensemble members, and the deterministic candidate P5 policy with frozen weight $\lambda = 0.0$ are strictly preserved and untouched.
2. **AgentView Isolation**: Agents ingest solely allowlisted, sanitized `AgentCaseView` records via [schemas/agent_view.py](file:///c:/Users/archi/OneDrive/Desktop/SignalGate/schemas/agent_view.py). Raw transaction columns, `isFraud`, true test labels, and evaluation DataFrames are structurally barred.
3. **Deterministic Supervisor**: [agents/supervisor.py](file:///c:/Users/archi/OneDrive/Desktop/SignalGate/agents/supervisor.py) uses deterministic action rules to dispatch the copilot only on escalated cases (`FRAUD_ALERT`, `MANUAL_REVIEW`, `HELD`, `DEFERRED`), keeping `ROUTINE` cases out of the agent path.
4. **Deterministic Claim Verifier**: [agents/claim_verifier.py](file:///c:/Users/archi/OneDrive/Desktop/SignalGate/agents/claim_verifier.py) enforces that every statement displayed to analysts is generated from a reviewed, registered template populated strictly by facts verified against the case audit record. Arbitrary LLM-generated prose is prohibited.
5. **Fail-Closed & Offline Resilience**: [agents/copilot.py](file:///c:/Users/archi/OneDrive/Desktop/SignalGate/agents/copilot.py) operates cleanly in offline/mock mode for deterministic reproducibility, reporting statuses `ok`, `unavailable`, `failed`, or `timed_out` without altering primary triage routing.
6. **Full Test Suite Integrity**: All 69 automated tests pass with zero failures.

---

## 2. G2 Foundation & Acceptance Criteria Status

The G2 empirical findings and acceptance criteria remain frozen and preserved:

### Preserved G2 Facts
* **Ensemble Architecture**: The era-bagged heterogeneous ensemble was retained; the seed-only ensemble was dropped under the pre-registered keep/drop rule ($\text{CI}_{\text{lower}} \le 0$).
* **Validation Recall Gain**: The era-bagged candidate achieves $+1.10\%$ pp recall improvement over B2 at the primary $1.5\times$ review budget with a $95\%$ CI of $[+0.241\%, +2.031\%]$.
* **P5 Decision Policy**: Operates with $\lambda = 0.0$ because empirical ablation proved that model disagreement adds no incremental predictive gain over ensemble risk ($\Delta\text{Recall} = -0.087\%$, $95\%$ CI $[-0.403\%, +0.237\%]$). Disagreement $u$ and $u_2$ are retained as explanatory/audit governance signals.
* **System Acceptance Criteria Status**:
  * **AC1**: **UNMET** (Measured $+1.10\%$ pp is below the $+2.0\%$ pp requirement).
  * **AC2**: **NOT ESTABLISHED** ($10\%$ workload reduction was not demonstrated).
  * **AC3–AC5**: **NOT MEASURED IN G2/G3** (Preserved for final system evaluation on IBM Z).
  * **Component Keep/Drop Rule**: **PASSED / RETAINED** ($\text{CI}_{\text{lower}} > 0$).

---

## 3. AgentView Input Boundary Enforcement

### Allowlist Specification ([schemas/agent_view.py](file:///c:/Users/archi/OneDrive/Desktop/SignalGate/schemas/agent_view.py))
`AgentCaseView` enforces `model_config = ConfigDict(extra="forbid", frozen=True)`:
* **Allowlisted Fields**: `record_id`, `p`, `u`, `u2`, `n`, `action`, `reason`, `record_hash`, `cfg_hash`, `split_hash`.
* **Prohibited Fields**: Any attempt to instantiate `AgentCaseView` with extra keys (such as `isFraud`, raw feature vectors, or column names) immediately raises a Pydantic `ValidationError`.
* **AST Static Analysis**: [tests/test_agent_guardrails.py](file:///c:/Users/archi/OneDrive/Desktop/SignalGate/tests/test_agent_guardrails.py) parses all files in `agents/` using Python's AST parser and confirms zero imports of `data`, `eval`, `models`, `pandas`, `numpy`, or `sklearn`, and zero references to forbidden identifiers.

---

## 4. Deterministic Supervisor & Case Copilot Architecture

```
[ Incoming Audit Record ]
          │
          ▼
[ AgentCaseView Allowlist ]
          │
          ▼
[ AgentSupervisor (agents/supervisor.py) ]
    ├── Action == "ROUTINE"       --> No agent invoked (Skip)
    └── Action == Escalated Queue  --> Dispatch Case Copilot
          │
          ▼
[ CaseCopilot (agents/copilot.py) ]
    ├── Generates Structured Claims
    └── Evaluates Input Provenance Hash
          │
          ▼
[ ClaimVerifier (agents/claim_verifier.py) ]
    ├── 1. Validate Claim Schema (Extra fields forbidden)
    ├── 2. Check Registered (Field, Operator)
    ├── 3. Evaluate Condition Against AgentCaseView
    ├── 4. Check Registered Template ID
    └── 5. Render Approved Template
          │
          ▼
[ Analyst Brief / AgentRecord ]
    ├── Status: "ok" | "unavailable" | "failed" | "timed_out"
    ├── Verified Claims (List[Claim])
    └── Input/Output Hashes (Audit Provenance)
```

---

## 5. Acceptance Test Results (AG1 – AG5)

All acceptance tests in [tests/test_agents_g3.py](file:///c:/Users/archi/OneDrive/Desktop/SignalGate/tests/test_agents_g3.py) passed:

| Acceptance Criterion | Description | Test Condition & Evidence | Target Standard | Measured Result | Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **AG1** | **Seeded False Claims Rejection** | 25 planted false claims spanning fabricated $p$, inverted inequalities, wrong actions, invalid templates, and unsupported operators. | 100% Block Rate ($1.0$) | **25/25 Rejected (100% Block Rate)** | **PASS** |
| **AG2** | **Honest Claims Acceptance** | 36 honest, factually true claims evaluated across 9 diverse cases. | False Block Rate $\le 5\%$ ($0.05$) | **0/36 Blocked (0.0% False Block Rate)** | **PASS** |
| **AG3** | **Verifier Integrity** | Arbitrary prose strings, extra Pydantic fields, and unregistered operators passed to verifier. | Must fail closed / reject | **100% Rejected / Blocked** | **PASS** |
| **AG4** | **Routing Invariance** | 100 test cases routed through `CandidateP5Policy` under 4 agent conditions (disabled, ok, failed, timed out). | Primary routing decisions byte-identical | **100% Byte-Identical across all 4 states** | **PASS** |
| **AG5** | **Label-Access Rejection** | Attempts to pass raw dicts with `isFraud`, raw feature names, or extra fields to Copilot. | Must fail closed (`TypeError` / `ValidationError`) | **100% Rejected / Failed Closed** | **PASS** |

### Additional Operational Tests
* **Copilot Offline Mode**: Clean mock/offline operation produces verified claims and valid SHA-256 provenance hashes without external API calls.
* **Timeout & Failure Handling**: Provider timeouts cleanly return `status="timed_out"`; exceptions cleanly return `status="failed"`. Primary routing decisions remain unaffected.
* **Supervisor Ineligibility**: `ROUTINE` auto-cleared cases are confirmed ineligible for agent dispatch.

---

## 6. S0 & Test-Data Governance Audit

* **Test Quarantine Intact**: The Kaggle/test partition ($118,108$ transactions) was **never accessed, evaluated, or referenced** during Gate G3.
* **Provenance Honesty**: Project documentation acknowledges that baseline B1/B2 metrics on the test partition were recorded in historical Gate G1 artifacts. No claim is made that the test set was pristine prior to G1.
* **No Label Exposure**: Zero ground truth labels (`isFraud`) were accessible or provided to agents, supervisors, or verifiers.

---

## 7. Cryptographic Configuration & Artifact Hashes

| Component | File / Path | SHA-256 Checksum |
| :--- | :--- | :--- |
| **Project Configuration** | [config.yaml](file:///c:/Users/archi/OneDrive/Desktop/SignalGate/config.yaml) | `e73a0e02fbd5411928ee41a0c70d71584ddc3a17ef9fc8711f318b99baed7f6e` |
| **P5 Candidate Policy Config** | [policy/p5_candidate.py](file:///c:/Users/archi/OneDrive/Desktop/SignalGate/policy/p5_candidate.py) | `10a2fd1f33ec388298f462d8390c8ca2e303d5c411be2643416322a8795b3c48` |
| **Train Partition Split** | [results/split_manifest.json](file:///c:/Users/archi/OneDrive/Desktop/SignalGate/results/split_manifest.json) | `ee8c38fd7e8b2af1b93a7824fd80f59c7811e5ce2ac1651500d51bf6e2e1f53a` |
| **Calibration Partition Split** | [results/split_manifest.json](file:///c:/Users/archi/OneDrive/Desktop/SignalGate/results/split_manifest.json) | `a1880e4f36558c33d77d0a1a2cf6b1dfe607a4983909364afff71ca84401e7bb` |
| **Validation Partition Split** | [results/split_manifest.json](file:///c:/Users/archi/OneDrive/Desktop/SignalGate/results/split_manifest.json) | `f824d80aea2e20f72e4ed8f06e6d119c7572caf50cf304dfb4224e8d990e7170` |
| **Held-Out Test Partition** | [results/split_manifest.json](file:///c:/Users/archi/OneDrive/Desktop/SignalGate/results/split_manifest.json) | `88d73a15fc60f9badfedc4909ede017de45a99f6c58798d54ab9c1dff90690f1` |

---

## 8. Automated Test Suite Execution Evidence

Command executed:
```powershell
python -m pytest -q
```

Output:
```text
.....................................................................    [100%]
69 passed in 0.97s
```

Test Breakdown:
* `tests/test_agent_guardrails.py`: 2 passed (AST isolation)
* `tests/test_agent_view.py`: 2 passed (schema allowlist)
* `tests/test_agents_g3.py`: 7 passed (AG1–AG5, lifecycle, supervisor)
* `tests/test_audit_chain.py`: 4 passed (HMAC chain integrity)
* `tests/test_base_models.py`: 10 passed (base models, partition guards)
* `tests/test_baselines.py`: 5 passed (B1 & B2 ranking)
* `tests/test_ensemble.py`: 9 passed (ensemble mathematics, determinism)
* `tests/test_policy.py`: 5 passed (Candidate P5 policy and routing)
* `tests/test_scaffolding.py`: 4 passed (G0 contracts)
* `tests/test_signals.py`: 17 passed (calibrators, ECE, signals)
* `tests/test_splits.py`: 4 passed (chronological boundaries)

---

## 9. Gate G3 Closure Checklist & Stop Condition

| Exit Condition | Verification Method | Status |
| :--- | :--- | :--- |
| **1. Frozen Decision Core** | G1/G2 models, P5 policy, and $\lambda=0.0$ untouched. | **PASS** |
| **2. AgentView Isolation** | Sanitized schema enforced; AST guardrails verified. | **PASS** |
| **3. Deterministic Supervisor** | Action-based dispatch implemented in `agents/supervisor.py`. | **PASS** |
| **4. Claim Verifier** | Template registration and factual verification in `agents/claim_verifier.py`. | **PASS** |
| **5. Case Copilot** | Offline mock mode and verified outputs in `agents/copilot.py`. | **PASS** |
| **6. AG1: False Claims** | 25/25 false claims blocked (100% block rate). | **PASS** |
| **7. AG2: Honest Claims** | 0/36 honest claims blocked (0.0% false block rate $\le 5\%$). | **PASS** |
| **8. AG3: Verifier Integrity** | Arbitrary prose, invalid schemas, and bad operators blocked. | **PASS** |
| **9. AG4: Routing Invariance** | Primary routing decisions byte-identical across agent states. | **PASS** |
| **10. AG5: Label-Access Rejection** | Prohibited objects fail closed with strict errors. | **PASS** |
| **11. Test Quarantine** | Test partition ($118,108$ rows) strictly uninspected during G3. | **PASS** |
| **12. Test Suite Integrity** | **69 passed, 0 failures** in pytest. | **PASS** |
| **13. Gate Boundary** | Execution halted at Gate G3. Gate G4 (Drift Sentinel) not initiated. | **PASS** |

**Gate G3 is COMPLETE and VERIFIED. Halted before Gate G4.**
