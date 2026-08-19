from langgraph.runtime import Runtime

from app.domain.actions.models import ActionType
from app.workflows.incident.context import IncidentWorkflowContext
from app.workflows.incident.nodes.common import StateUpdate, traced_node, workflow_runtime
from app.workflows.incident.state import IncidentWorkflowState


def propose_action(
    state: IncidentWorkflowState, runtime: Runtime[IncidentWorkflowContext]
) -> StateUpdate:
    action_value = state["proposed_action_type"]
    if action_value is None:
        raise ValueError("Action proposal is missing an action type")
    proposal_id = traced_node(
        runtime,
        "propose_action",
        lambda: workflow_runtime(runtime).propose_action(ActionType(action_value)),
    )
    return {"proposed_action_id": proposal_id, "current_node": "propose_action"}
