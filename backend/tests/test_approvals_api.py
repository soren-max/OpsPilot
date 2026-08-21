from langgraph.checkpoint.memory import InMemorySaver
from sqlalchemy.orm import Session

from app.application.approval_service import ApprovalService
from app.application.workflow_service import WorkflowService
from app.models import Permission, RolePermission
from tests.workflows.test_incident_workflow import create_incident, mock_action_service


def _waiting(db: Session, *, shared_checkpoint: bool = False) -> tuple[str, str]:
    incident_id = create_incident(db, "service unavailable")
    service = WorkflowService(
        db,
        checkpointer=None if shared_checkpoint else InMemorySaver(),
        action_service=mock_action_service("mock-service"),
    )
    workflow = service.start(incident_id, "operator", "approval-api")
    result = service.run(workflow.id)
    approval_id = result.state_references["approval_id"]
    assert isinstance(approval_id, str)
    return incident_id, approval_id


def test_approval_list_does_not_expose_checkpoint_or_executor(client: object, db: Session) -> None:
    incident_id, _ = _waiting(db)
    response = client.get(f"/api/v1/approvals?incident_id={incident_id}")  # type: ignore[attr-defined]
    assert response.status_code == 200
    item = response.json()["data"][0]
    assert "checkpoint" not in item
    assert "executor" not in item
    assert item["status"] == "PENDING"


def test_approval_api_permission_validation(client: object, db: Session) -> None:
    _, approval_id = _waiting(db)
    permission = db.query(Permission).filter_by(code="approval.decide").one()
    db.query(RolePermission).filter_by(permission_id=permission.id).delete()
    db.commit()

    response = client.post(  # type: ignore[attr-defined]
        f"/api/v1/approvals/{approval_id}/approve", json={"reason": "Authorized evidence"}
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "PERMISSION_DENIED"


def test_approval_api_approve_resumes_workflow(client: object, db: Session) -> None:
    _, approval_id = _waiting(db, shared_checkpoint=True)

    response = client.post(  # type: ignore[attr-defined]
        f"/api/v1/approvals/{approval_id}/approve",
        json={"reason": "Diagnosis and evidence support the bounded restart"},
    )

    assert response.status_code == 200
    assert response.json()["data"]["status"] == "APPROVED"
    approval = ApprovalService(db).get(approval_id)
    workflow = WorkflowService(db).get(approval.workflow_run_id)
    assert response.json()["data"]["resumed_at"] is not None, workflow.last_error
