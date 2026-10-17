# SignalGate Architecture Specification
## Shift-Aware Fraud Triage for IBM Z Datathon 2026

SignalGate is a shift-aware fraud triage decision-support simulation designed for high-throughput, enterprise transaction environments on IBM Z and LinuxONE. It demonstrates resilient fraud detection, uncertainty calibration, and human-in-the-loop governance under real-world distribution shift.

---

## 1. System Invariants and Non-Negotiable Boundaries

SignalGate is governed by six strict architectural boundaries:

1. **Deterministic Execution Core**  
   All numerical calculations, signal transformations, uncertainty scoring, and queue-routing decisions are executed purely via deterministic Python code. No non-deterministic LLM output or probabilistic routing governs transaction triage.

2. **Ground Truth Isolation (`isFraud` Invariant)**  
   The target ground truth label `isFraud` is strictly quarantined. Under no circumstances may `isFraud` be ingested, referenced, or used as a feature during signal generation, model inference, or routing logic. It exists solely in offline, frozen evaluation benchmarks.

3. **Sanitized Audit Record Boundary for LLM Agents**  
   LLM agents function exclusively as post-decision audit and explanatory support tools. Agents only ingest sanitized audit records (with PII and sensitive transactional payloads stripped). Agents do not make automated transaction approval or blocking decisions.

4. **Immutable Frozen Test Evaluation**  
   The evaluation harness and benchmark datasets are strictly frozen. Autonomous agents and adaptive components possess zero write permissions or mutation pathways to test datasets, benchmark labels, or evaluation metrics.

5. **Drift Sentinel Governance & Human-in-the-Loop Replay**  
   When the Drift Sentinel detects statistical distribution shifts and proposes policy or threshold recalibrations, the proposal cannot be enacted autonomously. It requires:
   - Complete deterministic replay on validation windows.
   - Explicit human sign-off via a cryptographic or audit-logged approval record.

6. **Decision-Support Simulation Scope**  
   SignalGate is an analytical decision-support and workflow simulation. It is not connected to live settlement rails or automated payment-blocking engines.

---

## 2. Component Layout & Directory Architecture

```
SignalGate/
├── agents/             # Post-decision LLM audit and explanation agents (sanitized records only)
├── governance/         # Drift Sentinel policies, deterministic validation replay, human sign-off logs
├── schemas/            # Pydantic data contracts (transactions, signals, sanitized audit events)
├── models/             # Statistical and ML scoring engines
│   └── signals/        # Specialized shift, uncertainty, and anomaly signal generators
├── data/               # Transaction datasets (raw, partitioned, and shift splits)
├── eval/               # Frozen test harnesses, cost-utility scoring, and latency benchmarks
├── policy/             # Deterministic triage routing matrices and threshold definitions
├── app/                # Decision-support analyst simulation dashboard
├── infra/              # IBM Z / LinuxONE deployment scripts and container definitions
├── figs/               # Architecture diagrams and performance plots
├── results/            # Run artifacts, validation replays, and benchmark outputs
├── docs/               # System documentation, specifications, and architecture guides
├── scripts/            # Operational, ingestion, and verification utilities
└── tests/              # Automated test suite (unit, integration, invariance checks)
```

---

## 3. Data Flow Overview

```
[ Incoming Transaction ]
         │
         ▼
[ Schema Validation (schemas/) ]
         │
         ▼
[ Deterministic Feature & Signal Extraction (models/signals/) ]
  * Strict Invariant: isFraud is completely excluded
         │
         ▼
[ Deterministic Triage Router (policy/) ]
  ├── Low Risk & High Certainty     --> Tier 1: Auto-Clear Queue
  ├── Elevated Risk or Ambiguity    --> Tier 2: Standard Analyst Audit Queue
  └── High Drift or Extreme Anomaly  --> Tier 3: Senior Escalation Queue
         │
         ▼
[ Sanitization Engine (schemas/) ]
         │ (PII & Raw Identifiers Scrubbed)
         ▼
[ Audit & Explanation Agent (agents/) ] --> Analyst Decision-Support Summary
         │
         ▼
[ Drift Sentinel (governance/) ]
  * If shift threshold exceeded:
      - Generates recalibration proposal
      - Triggers deterministic validation replay
      - Awaits human sign-off
```

---

## 4. Governance & Verification Lifecycle

- **Offline Baseline Evaluation**: Evaluated against frozen test splits in `eval/` with fixed random seeds and zero leakage.
- **Auditability**: Every triage routing decision emits a reproducible, deterministic record with timestamp, signal vector, calibrated confidence interval, and assigned triage tier.
- **Human Authority**: Human fraud analysts retain full authority to override routing and confirm any adaptation proposals triggered by concept or covariate shifts.
