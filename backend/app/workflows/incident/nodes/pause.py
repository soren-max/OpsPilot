from langgraph.runtime import Runtime

from app.domain.audit.models import AuditEventType
from app.workflows.incident.context import IncidentWorkflowContext
from app.workflows.incident.nodes.common import StateUpdate, traced_node, workflow_runtime
from app.workflows.incident.state import IncidentWorkflowState, WorkflowStatus


def approval_required(
    state: IncidentWorkflowState, runtime: Runtime[IncidentWorkflowContext]
) -> StateUpdate:
    del state
    def pause() -> None:
        workflow_runtime(runtime).audit_workflow(
            AuditEventType.WORKFLOW_PAUSED,
            "Workflow paused at the approval boundary",
            WorkflowStatus.WAITING_APPROVAL.value,
        )

    traced_node(runtime, "approval_required", pause)
    return {
        "workflow_status": WorkflowStatus.WAITING_APPROVAL.value,
        "current_node": "approval_required",
    }
