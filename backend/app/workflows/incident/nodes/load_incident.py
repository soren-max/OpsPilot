from langgraph.runtime import Runtime

from app.workflows.incident.context import IncidentWorkflowContext
from app.workflows.incident.nodes.common import StateUpdate, traced_node, workflow_runtime
from app.workflows.incident.state import IncidentWorkflowState, WorkflowStatus


def load_incident(
    state: IncidentWorkflowState, runtime: Runtime[IncidentWorkflowContext]
) -> StateUpdate:
    del state
    version, evidence_ids = traced_node(
        runtime, "load_incident", lambda: workflow_runtime(runtime).load_incident()
    )
    return {
        "incident_version": version,
        "evidence_ids": evidence_ids,
        "workflow_status": WorkflowStatus.RUNNING.value,
        "current_node": "load_incident",
    }
