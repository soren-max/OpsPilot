from langgraph.runtime import Runtime

from app.domain.actions.models import ActionType
from app.workflows.incident.context import IncidentWorkflowContext
from app.workflows.incident.nodes.common import StateUpdate, traced_node, workflow_runtime
from app.workflows.incident.state import IncidentWorkflowState


def execute(
    state: IncidentWorkflowState, runtime: Runtime[IncidentWorkflowContext]
) -> StateUpdate:
    action_value = state["proposed_action_type"]
    if action_value is None:
        raise ValueError("Execution requires an action type")
    execution_id, status = traced_node(
        runtime,
        "execute",
        lambda: workflow_runtime(runtime).execute(ActionType(action_value)),
    )
    return {
        "execution_task_id": execution_id,
        "verification_status": status,
        "current_node": "execute",
    }
