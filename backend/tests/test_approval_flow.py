from sqlalchemy import select
from sqlalchemy.orm import Session

from app.adapters.mock import MockActionExecutor
from app.application import ActionService
from app.core.config import Settings
from app.core.enums import ApprovalStatus, TaskStatus
from app.core.security import hash_password
from app.domain.actions.policy import ActionPolicyEngine
from app.models import AuditLog, OperationRequest, OperationTask, Role, User, UserRole
from app.services import approvals as approvals_module
from app.services import operations as operations_module
from app.services.worker import WorkerService

ENV = "00000000-0000-0000-0000-000000000001"
SERVICE = "20000000-0000-0000-0000-000000000001"
HOST = "10000000-0000-0000-0000-000000000001"


def approval_settings() -> Settings:
    return Settings(
        write_operations_enabled=True,
        production_operations_enabled=False,
        approval_required_for_write=True,
        allowed_actions="status,restart",
        _env_file=None,
    )


def request_body(action: str = "restart") -> dict[str, object]:
    return {
        "operation": {
            "environment_id": ENV,
            "action": action,
            "scope": "service_hosts",
            "service_id": SERVICE,
            "host_ids": [HOST],
        },
        "reason": "scheduled mock maintenance",
    }


def login_as_approver(client, db: Session) -> User:
    role = db.scalar(select(Role).where(Role.code == "admin"))
    assert role is not None
    user = User(
        username="approver",
        display_name="Approver",
        password_hash=hash_password("approver-test-password"),
        enabled=True,
        status="ACTIVE",
    )
    db.add(user)
    db.flush()
    db.add(UserRole(user_id=user.id, role_id=role.id))
    db.commit()
    login = client.post(
        "/api/v1/auth/login",
        json={"username": "approver", "password": "approver-test-password"},
    )
    assert login.status_code == 200
    client.headers["Authorization"] = f"Bearer {login.json()['access_token']}"
    return user


def configure_approval(monkeypatch, settings: Settings) -> None:
    monkeypatch.setattr(approvals_module, "get_settings", lambda: settings)
    monkeypatch.setattr(operations_module, "get_settings", lambda: settings)


def action_service() -> ActionService:
    return ActionService(
        ActionPolicyEngine(frozenset({"mock-host-ok"})), MockActionExecutor()
    )


def test_request_approve_execute_and_duplicate_protection(client, db, monkeypatch) -> None:
    settings = approval_settings()
    configure_approval(monkeypatch, settings)
    created = client.post(
        "/api/v1/operation-requests",
        json=request_body(),
        headers={"Idempotency-Key": "approval-flow-0001"},
    )
    assert created.status_code == 201
    request_id = created.json()["data"]["id"]
    assert created.json()["data"]["status"] == "PENDING"

    self_review = client.post(
        f"/api/v1/operation-requests/{request_id}/approve", json={"comment": "self"}
    )
    assert self_review.status_code == 403
    assert self_review.json()["error"]["code"] == "SELF_APPROVAL_FORBIDDEN"

    login_as_approver(client, db)
    approved = client.post(
        f"/api/v1/operation-requests/{request_id}/approve",
        json={"comment": "approved for mock execution"},
    )
    assert approved.status_code == 200
    data = approved.json()["data"]
    assert data["status"] == "APPROVED"
    assert data["task_id"]
    assert data["approvals"][0]["decision"] == "APPROVED"

    duplicate = client.post(f"/api/v1/operation-requests/{request_id}/approve", json={})
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "APPROVAL_ALREADY_DECIDED"

    assert WorkerService(db, action_service(), settings).run_once()
    task = db.get(OperationTask, data["task_id"])
    assert task is not None and task.status is TaskStatus.SUCCEEDED
    audits = list(db.scalars(select(AuditLog).order_by(AuditLog.created_at)))
    event_types = {item.event_type for item in audits}
    assert {
        "OPERATION_REQUEST_CREATED",
        "OPERATION_REQUEST_APPROVED",
        "WRITE_EXECUTION_AUTHORIZED",
    } <= event_types


def test_request_reject_and_requester_cancel_are_audited(client, db, monkeypatch) -> None:
    settings = approval_settings()
    configure_approval(monkeypatch, settings)
    first = client.post(
        "/api/v1/operation-requests",
        json=request_body(),
        headers={"Idempotency-Key": "approval-cancel-0001"},
    )
    first_id = first.json()["data"]["id"]
    cancelled = client.post(f"/api/v1/operation-requests/{first_id}/cancel")
    assert cancelled.status_code == 200
    assert cancelled.json()["data"]["status"] == "CANCELLED"

    second = client.post(
        "/api/v1/operation-requests",
        json=request_body(),
        headers={"Idempotency-Key": "approval-reject-0001"},
    )
    second_id = second.json()["data"]["id"]
    login_as_approver(client, db)
    rejected = client.post(
        f"/api/v1/operation-requests/{second_id}/reject",
        json={"comment": "maintenance window closed"},
    )
    assert rejected.status_code == 200
    assert rejected.json()["data"]["status"] == "REJECTED"
    events = set(db.scalars(select(AuditLog.event_type)))
    assert "OPERATION_REQUEST_CANCELLED" in events
    assert "OPERATION_REQUEST_REJECTED" in events


def test_worker_rechecks_approval_before_executor_invocation(client, db, monkeypatch) -> None:
    settings = approval_settings()
    configure_approval(monkeypatch, settings)
    created = client.post(
        "/api/v1/operation-requests",
        json=request_body(),
        headers={"Idempotency-Key": "approval-worker-0001"},
    )
    request_id = created.json()["data"]["id"]
    login_as_approver(client, db)
    approved = client.post(f"/api/v1/operation-requests/{request_id}/approve", json={}).json()[
        "data"
    ]

    operation_request = db.get(OperationRequest, request_id)
    assert operation_request is not None
    operation_request.status = ApprovalStatus.CANCELLED
    db.commit()

    assert WorkerService(db, action_service(), settings).run_once()
    task = db.get(OperationTask, approved["task_id"])
    assert task is not None
    assert task.status is TaskStatus.FAILED
    assert task.error_message and "APPROVAL_INVALIDATED" in task.error_message


def test_test_environment_allows_single_admin_self_approval(client, db, monkeypatch) -> None:
    settings = approval_settings()
    settings.allow_self_approval = True
    configure_approval(monkeypatch, settings)
    created = client.post(
        "/api/v1/operation-requests",
        json=request_body(),
        headers={"Idempotency-Key": "approval-self-test-0001"},
    )
    request_id = created.json()["data"]["id"]
    approved = client.post(
        f"/api/v1/operation-requests/{request_id}/approve",
        json={"comment": "isolated TEST exercise"},
    )
    assert approved.status_code == 200
    assert approved.json()["data"]["status"] == "APPROVED"
    task_id = approved.json()["data"]["task_id"]
    assert task_id
    assert WorkerService(db, action_service(), settings).run_once()
    task = db.get(OperationTask, task_id)
    assert task is not None and task.status is TaskStatus.SUCCEEDED
