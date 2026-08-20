from langgraph.runtime import Runtime

from app.domain.actions.models import RiskLevel
from app.workflows.incident.context import IncidentWorkflowContext
from app.workflows.incident.nodes.common import StateUpdate, traced_node, workflow_runtime
from app.workflows.incident.state import IncidentWorkflowState, WorkflowStatus


def finalize(
    state: IncidentWorkflowState, runtime: Runtime[IncidentWorkflowContext]
) -> StateUpdate:
    successful = not state["action_needed"] or (
        state["risk_level"] != RiskLevel.FORBIDDEN.value
        and state["verification_status"] == "SUCCEEDED"
    )
    inconclusive = state["insufficient_evidence"]
    version = traced_node(
        runtime,
        "finalize",
        lambda: workflow_runtime(runtime).finalize(
            state["incident_version"],
            successful=successful,
            inconclusive=inconclusive,
        ),
    )
    return {
        "incident_version": version,
        "workflow_status": (
            WorkflowStatus.SUCCEEDED.value
            if successful or inconclusive
            else WorkflowStatus.FAILED.value
        ),
        "current_node": "finalize",
        "last_error": (
            "POLICY_BLOCKED"
            if state["action_needed"] and state["risk_level"] == RiskLevel.FORBIDDEN.value
            else None
        ),
    }
