from langgraph.runtime import Runtime

from app.domain.actions.models import ActionType
from app.workflows.incident.context import IncidentWorkflowContext
from app.workflows.incident.nodes.common import StateUpdate, traced_node, workflow_runtime
from app.workflows.incident.state import IncidentWorkflowState


def assess_risk(
    state: IncidentWorkflowState, runtime: Runtime[IncidentWorkflowContext]
) -> StateUpdate:
    action_value = state["proposed_action_type"]
    if action_value is None:
        raise ValueError("Risk assessment requires an action type")
    assessment = traced_node(
        runtime,
        "assess_risk",
        lambda: workflow_runtime(runtime).assess_risk(ActionType(action_value)),
    )
    return {
        "risk_level": assessment.risk_level.value,
        "approval_required": assessment.approval_required,
        "current_node": "assess_risk",
    }
