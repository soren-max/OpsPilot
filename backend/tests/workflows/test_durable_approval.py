import pytest
from langgraph.checkpoint.memory import InMemorySaver
from sqlalchemy.orm import Session

from app.application.approval_service import ApprovalService
from app.application.workflow_service import WorkflowService
from app.core.errors import ConflictError
from app.domain.approvals import ApprovalActor, ApprovalDecision, ApprovalStatus
from app.domain.audit.models import AuditEventType
from app.repositories.workflow_models import WorkflowRunStatus
from tests.workflows.test_incident_workflow import create_incident, mock_action_service


def _waiting(db: Session, saver: InMemorySaver) -> tuple[WorkflowService, str, str]:
    incident_id = create_incident(db, "service unavailable")
    service = WorkflowService(
        db,
        checkpointer=saver,
        action_service=mock_action_service("mock-service"),
    )
    workflow = service.start(incident_id, "operator", "durable-approval")
    result = service.run(workflow.id)
    approval_id = result.state_references["approval_id"]
    assert isinstance(approval_id, str)
    assert result.status is WorkflowRunStatus.WAITING
    return service, result.id, approval_id


def test_approval_lifecycle_records_identity_and_audit(db: Session) -> None:
    saver = InMemorySaver()
    workflow_service, workflow_id, approval_id = _waiting(db, saver)
    actor = ApprovalActor(actor_id="user-7", display_name="On-call Engineer")

    approval = ApprovalService(db).approve(approval_id, actor, "Evidence supports restart")

    assert approval.status is ApprovalStatus.APPROVED
    assert approval.decision is ApprovalDecision.APPROVE
    assert approval.approver_identity == "user-7"
    assert approval.resolved_at is not None
    result = workflow_service.resume(approval_id)
    assert result.status is WorkflowRunStatus.SUCCEEDED
    events = workflow_service.runs.list_audit_events(workflow_id)
    event_types = [event.event_type for event in events]
    assert AuditEventType.APPROVAL_REQUESTED in event_types
    assert AuditEventType.APPROVAL_APPROVED in event_types
    assert AuditEventType.WORKFLOW_RESUMED in event_types


def test_reject_resumes_to_failure_without_execution(db: Session) -> None:
    saver = InMemorySaver()
    workflow_service, _, approval_id = _waiting(db, saver)
    actor = ApprovalActor(actor_id="user-8", display_name="Incident Commander")
    ApprovalService(db).reject(approval_id, actor, "Risk exceeds incident impact")

    result = workflow_service.resume(approval_id)

    assert result.status is WorkflowRunStatus.FAILED
    assert result.execution_task_id is None
    assert result.last_error == "APPROVAL_REJECTED"


def test_duplicate_approval_and_resume_are_safe_across_service_restart(db: Session) -> None:
    saver = InMemorySaver()
    _, workflow_id, approval_id = _waiting(db, saver)
    actor = ApprovalActor(actor_id="user-9", display_name="Primary On-call")
    approvals = ApprovalService(db)
    approvals.approve(approval_id, actor, "Approved once")
    with pytest.raises(ConflictError, match="already resolved"):
        approvals.approve(approval_id, actor, "Approved twice")

    restarted = WorkflowService(
        db,
        checkpointer=saver,
        action_service=mock_action_service("mock-service"),
    )
    first = restarted.resume(approval_id)
    execution_task_id = first.execution_task_id
    second = restarted.resume(approval_id)

    assert first.id == workflow_id
    assert first.status is WorkflowRunStatus.SUCCEEDED
    assert execution_task_id is not None
    assert second.execution_task_id == execution_task_id
    assert ApprovalService(db).get(approval_id).resumed_at is not None
