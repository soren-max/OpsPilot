from langgraph.runtime import Runtime

from app.workflows.incident.context import IncidentWorkflowContext
from app.workflows.incident.nodes.common import StateUpdate, traced_node
from app.workflows.incident.state import IncidentWorkflowState


def verify(
    state: IncidentWorkflowState, runtime: Runtime[IncidentWorkflowContext]
) -> StateUpdate:
    status = traced_node(runtime, "verify", lambda: state["verification_status"] or "FAILED")
    return {"verification_status": status, "current_node": "verify"}
