"""Deterministic agent supervisor for SignalGate Gate G3.

Governs agent dispatch using strict, deterministic rules based on case triage action.

Key Invariants:
1. Purely deterministic logic; no LLM selects agents or makes routing decisions.
2. Agents run strictly outside the primary triage decision path.
3. Routine cases are not eligible for copilot dispatch (saving compute and focus).
4. Escalated cases (FRAUD_ALERT, MANUAL_REVIEW, HELD, DEFERRED) trigger copilot brief.
5. Copilot outcome (success, failure, timeout) never modifies primary routing decisions.
"""

from __future__ import annotations

from typing import Literal

from agents.copilot import CaseCopilot
from schemas.agent_view import AgentCaseView
from schemas.contracts import Action, AgentRecord

ELIGIBLE_ACTIONS: set[Action] = {
    "FRAUD_ALERT",
    "MANUAL_REVIEW",
    "HELD",
    "DEFERRED",
}


class AgentSupervisor:
    """Deterministic supervisor governing agent eligibility and execution."""

    def __init__(
        self,
        copilot: CaseCopilot | None = None,
        enabled_agents: set[str] | None = None,
    ) -> None:
        self.copilot = copilot or CaseCopilot()
        self.enabled_agents = enabled_agents if enabled_agents is not None else {"case_copilot"}

    def is_eligible(self, case_view: AgentCaseView) -> bool:
        """Determine whether a case warrants post-decision agent analysis."""
        if not isinstance(case_view, AgentCaseView):
            return False
        return case_view.action in ELIGIBLE_ACTIONS

    def select_agent(self, case_view: AgentCaseView) -> Literal["case_copilot"] | None:
        """Deterministically select appropriate agent for an eligible case."""
        if not self.is_eligible(case_view):
            return None
        if "case_copilot" in self.enabled_agents:
            return "case_copilot"
        return None

    def dispatch(self, case_view: AgentCaseView) -> AgentRecord | None:
        """Safely dispatch case to eligible agent without altering routing state."""
        agent_choice = self.select_agent(case_view)
        if agent_choice is None:
            return None

        if agent_choice == "case_copilot":
            return self.copilot.generate_brief(case_view)

        return None
