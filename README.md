# SignalGate: Shift-Aware Fraud Triage for IBM Z Datathon 2026

SignalGate is a shift-aware fraud triage decision-support simulation engineered for IBM Z and LinuxONE enterprise architectures. The system provides resilient fraud detection under temporal and covariate distribution shift by coupling deterministic statistical signal extraction with calibrated triage routing and human-in-the-loop governance.

> **Scope Notice**: SignalGate is an analytical decision-support simulation designed to optimize fraud triage queues and evaluate shift resilience. It is **not** a live settlement or automated payment-blocking system.

---

## Non-Negotiable Architectural Invariants

SignalGate adheres strictly to the following architectural boundaries:

1. **Deterministic Execution Core**: All numerical calculations, statistical calibrations, and queue-routing policies are computed via deterministic Python logic.
2. **Ground Truth Isolation**: The label `isFraud` is strictly an offline evaluation benchmark. It is **never** accessible as a feature or routing parameter.
3. **Sanitized Agent Boundary**: LLM agents operate purely as post-decision audit and explanatory support tools, ingesting strictly sanitized audit records stripped of PII.
4. **Frozen Evaluation Integrity**: Automated agents and adaptive processes have zero write access to frozen evaluation datasets or benchmark harnesses.
5. **Drift Sentinel Governance**: Shift detection proposals require deterministic validation replay and explicit human-in-the-loop sign-off before any policy updates.
6. **Decision-Support Simulation**: The platform simulates queue management and analytical decision support rather than automated payment interruption.

---

## Repository Structure

```
SignalGate/
├── agents/             # Post-decision explanation and audit LLM agents
├── governance/         # Drift Sentinel policies, replay validation, and sign-offs
├── schemas/            # Pydantic schemas and data contracts
├── models/             # Core statistical models and feature pipelines
│   └── signals/        # Specialized shift, uncertainty, and anomaly signal generators
├── data/               # Data store for raw, processed, and shift split sets
├── eval/               # Frozen test harnesses, cost-utility metrics, and evaluation logic
├── policy/             # Deterministic triage routing tables and tier thresholds
├── app/                # Streamlit decision-support dashboard for fraud analysts
├── infra/              # IBM Z / LinuxONE deployment specifications and container configs
├── figs/               # Architecture diagrams and benchmark figures
├── results/            # Run outputs, validation replay artifacts, and experiment logs
├── docs/               # System documentation and architectural specifications
├── scripts/            # Pipeline orchestration and verification scripts
└── tests/              # Automated test suite
```

---

## Environment Setup

### 1. Prerequisites
- Python 3.10+
- `pip` and `virtualenv`

### 2. Creating the Virtual Environment

#### On Windows (PowerShell):
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

*(Optional: For machine learning and simulation dashboard dependencies)*
```powershell
pip install -r requirements-ml.txt
```

#### On Linux / macOS (Bash):
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
# Optional ML dependencies:
pip install -r requirements-ml.txt
```

### 3. Running Verification Tests

```bash
pytest tests/
```

---

## Project Status

- **Step 0**: Repository scaffolding and architectural invariants initialized.
- **Next Step**: Step 1 implementation pending user confirmation.
