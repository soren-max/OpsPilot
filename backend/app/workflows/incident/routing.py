from typing import Literal

from app.domain.actions.models import RiskLevel
from app.workflows.incident.state import IncidentWorkflowState


def route_after_diagnosis(state: IncidentWorkflowState) -> Literal["finalize", "propose_action"]:
    return "propose_action" if state["action_needed"] else "finalize"


def route_after_risk(
    state: IncidentWorkflowState,
) -> Literal["finalize", "execute", "approval_required"]:
    if state["approval_required"]:
        return "approval_required"
    if state["risk_level"] == RiskLevel.FORBIDDEN.value:
        return "finalize"
    return "execute"


def route_after_verify(state: IncidentWorkflowState) -> Literal["finalize", "failure"]:
    return "finalize" if state["verification_status"] == "SUCCEEDED" else "failure"
