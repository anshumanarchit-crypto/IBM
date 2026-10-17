"""SignalGate Agent Layer package.

Contains:
- CaseCopilot: post-decision analyst brief generation under AgentView boundary.
- ClaimVerifier: deterministic verification of structured claims.
- AgentSupervisor: deterministic agent eligibility and dispatch.
- VerificationResult: individual claim validation outcome.
- DriftSentinel: advisory drift detection agent generating adaptation proposals.
- ALLOWLISTED_CONFIG_KEYS: registered configuration keys permitted in proposals.
"""

from agents.claim_verifier import ClaimVerifier, VerificationResult
from agents.copilot import CaseCopilot
from agents.drift_sentinel import ALLOWLISTED_CONFIG_KEYS, DriftSentinel
from agents.supervisor import AgentSupervisor

__all__ = [
    "CaseCopilot",
    "ClaimVerifier",
    "AgentSupervisor",
    "VerificationResult",
    "DriftSentinel",
    "ALLOWLISTED_CONFIG_KEYS",
]
