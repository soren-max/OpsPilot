from langgraph.runtime import Runtime

from app.workflows.incident.context import IncidentWorkflowContext
from app.workflows.incident.nodes.common import StateUpdate, traced_node, workflow_runtime
from app.workflows.incident.state import IncidentWorkflowState, WorkflowStatus


def failure(
    state: IncidentWorkflowState, runtime: Runtime[IncidentWorkflowContext]
) -> StateUpdate:
    version = traced_node(
        runtime,
        "failure",
        lambda: workflow_runtime(runtime).finalize(
            state["incident_version"], successful=False
        ),
    )
    return {
        "incident_version": version,
        "workflow_status": WorkflowStatus.FAILED.value,
        "last_error": "VERIFICATION_FAILED",
        "current_node": "failure",
    }
