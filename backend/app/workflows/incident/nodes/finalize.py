from langgraph.runtime import Runtime

from app.domain.actions.models import RiskLevel
from app.workflows.incident.context import IncidentWorkflowContext
from app.workflows.incident.nodes.common import StateUpdate, traced_node, workflow_runtime
from app.workflows.incident.state import IncidentWorkflowState, WorkflowStatus


def finalize(
    state: IncidentWorkflowState, runtime: Runtime[IncidentWorkflowContext]
) -> StateUpdate:
    action_needed = state["action_needed"]
    policy_blocked = state["risk_level"] == RiskLevel.FORBIDDEN.value
    verified = state["verification_status"] == "SUCCEEDED"
    # Resolution requires an independently verified remediation. Proposing no action, being
    # blocked by policy, failing verification, or lacking evidence never resolves an incident.
    successful = bool(action_needed and not policy_blocked and verified)
    inconclusive = bool(state["insufficient_evidence"] or not action_needed)
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
        # An inconclusive run completes without failing the workflow, but the incident stays
        # active: workflow completion is not incident resolution.
        "workflow_status": (
            WorkflowStatus.SUCCEEDED.value
            if successful or inconclusive
            else WorkflowStatus.FAILED.value
        ),
        "current_node": "finalize",
        "last_error": "POLICY_BLOCKED" if action_needed and policy_blocked else None,
    }