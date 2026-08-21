from langgraph.runtime import Runtime
from langgraph.types import interrupt

from app.domain.audit.models import AuditEventType
from app.workflows.incident.context import IncidentWorkflowContext
from app.workflows.incident.nodes.common import StateUpdate, traced_node, workflow_runtime
from app.workflows.incident.state import IncidentWorkflowState, WorkflowStatus


def approval_required(
    state: IncidentWorkflowState, runtime: Runtime[IncidentWorkflowContext]
) -> StateUpdate:
    action_fingerprint = state["proposed_action_id"]
    if action_fingerprint is None:
        raise ValueError("Approval requires an action fingerprint")

    def pause() -> tuple[str, object]:
        capabilities = workflow_runtime(runtime)
        approval_id = capabilities.request_approval(action_fingerprint)
        capabilities.audit_workflow(
            AuditEventType.WORKFLOW_PAUSED,
            "Workflow paused at the approval boundary",
            WorkflowStatus.WAITING_APPROVAL.value,
        )
        decision = interrupt(
            {"approval_id": approval_id, "workflow_id": state["workflow_id"]}
        )
        return approval_id, decision

    approval_id, raw_decision = traced_node(runtime, "approval_required", pause)
    if not isinstance(raw_decision, dict) or raw_decision.get("approval_id") != approval_id:
        raise ValueError("Resume payload does not match the interrupted approval")
    decision = raw_decision.get("decision")
    if decision not in {"APPROVE", "REJECT"}:
        raise ValueError("Resume payload has an invalid approval decision")
    return {
        "workflow_status": WorkflowStatus.RUNNING.value,
        "current_node": "approval_required",
        "approval_id": approval_id,
        "approval_decision": decision,
        "last_error": "APPROVAL_REJECTED" if decision == "REJECT" else None,
    }
