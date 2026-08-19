import json

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.enums import OperationAction, TargetStatus
from app.core.security import hash_password
from app.db.base import utc_now
from app.executors.base import BaseExecutor, ExecutionRequest, ExecutionResult
from app.models import AuditLog, Permission, Role, RolePermission, User, UserRole
from app.services.worker import WorkerService

ENV = "00000000-0000-0000-0000-000000000001"
SERVICE = "20000000-0000-0000-0000-000000000001"
HOST = "10000000-0000-0000-0000-000000000001"


def operation_payload() -> dict[str, object]:
    return {
        "environment_id": ENV,
        "action": "status",
        "scope": "service_hosts",
        "service_id": SERVICE,
        "host_ids": [HOST],
        "parameters": {},
    }


def test_task_log_and_audit_reads_require_login(client) -> None:
    client.headers.clear()
    for path in ("/api/v1/tasks", "/api/v1/tasks/missing/logs", "/api/v1/audits"):
        result = client.get(path)
        assert result.status_code == 401
        assert result.json()["error"]["code"] == "UNAUTHORIZED"


def test_catalog_reads_require_login(client) -> None:
    client.headers.clear()
    for path in (
        "/api/v1/environments",
        "/api/v1/services",
        f"/api/v1/services/{SERVICE}",
        f"/api/v1/services/{SERVICE}/hosts",
        "/api/v1/hosts",
        f"/api/v1/hosts/{HOST}",
        f"/api/v1/hosts/{HOST}/services",
    ):
        result = client.get(path)
        assert result.status_code == 401
        assert result.json()["error"]["code"] == "UNAUTHORIZED"


def test_catalog_reads_enforce_rbac_and_allow_authorized_users(client, db: Session) -> None:
    role = Role(code="catalog-service-only", name="Service catalog only")
    user = User(
        username="catalog-user",
        display_name="Catalog",
        password_hash=hash_password("catalog-user-password"),
        enabled=True,
        status="ACTIVE",
    )
    service_read = db.scalar(select(Permission).where(Permission.code == "service.read"))
    assert service_read is not None
    db.add_all([role, user])
    db.flush()
    db.add_all(
        [
            UserRole(user_id=user.id, role_id=role.id),
            RolePermission(role_id=role.id, permission_id=service_read.id),
        ]
    )
    db.commit()
    login = client.post(
        "/api/v1/auth/login",
        json={"username": "catalog-user", "password": "catalog-user-password"},
    )
    client.headers["Authorization"] = f"Bearer {login.json()['access_token']}"

    assert client.get("/api/v1/environments").status_code == 200
    assert client.get("/api/v1/services").status_code == 200
    denied = client.get("/api/v1/hosts")
    assert denied.status_code == 403
    assert denied.json()["error"]["code"] == "PERMISSION_DENIED"


def test_read_permissions_fail_closed_and_are_audited(client, db: Session) -> None:
    role = Role(code="no-read", name="No read access")
    user = User(
        username="limited-user",
        display_name="Limited",
        password_hash=hash_password("limited-user-password"),
        enabled=True,
        status="ACTIVE",
    )
    db.add_all([role, user])
    db.flush()
    db.add(UserRole(user_id=user.id, role_id=role.id))
    db.commit()
    login = client.post(
        "/api/v1/auth/login",
        json={"username": "limited-user", "password": "limited-user-password"},
    )
    client.headers["Authorization"] = f"Bearer {login.json()['access_token']}"

    tasks = client.get("/api/v1/tasks")
    audits = client.get("/api/v1/audits")
    assert tasks.status_code == audits.status_code == 403
    assert tasks.json()["error"]["code"] == "PERMISSION_DENIED"
    assert audits.json()["error"]["code"] == "PERMISSION_DENIED"
    denied = list(db.scalars(select(AuditLog).where(AuditLog.event_type == "READ_ACCESS_DENIED")))
    assert len(denied) == 2


class SensitiveOutputExecutor(BaseExecutor):
    executor_type = "mock"
    supported_actions = frozenset({OperationAction.STATUS})

    def _execute(self, request: ExecutionRequest) -> ExecutionResult:
        return ExecutionResult(
            TargetStatus.SUCCEEDED,
            (
                f"host={request.host_name} account=admin password=hunter2 "
                "command=services.sh start --token raw-token"
            ),
            "stderr from mock-host-ok at 10.2.3.4 secret=raw-secret",
            1,
            service_state="RUNNING",
        )


def test_execution_and_audit_reads_are_defensively_redacted(client, db: Session) -> None:
    created = client.post("/api/v1/operations", json=operation_payload())
    task_id = created.json()["data"]["task_id"]
    assert WorkerService(db, SensitiveOutputExecutor(), get_settings()).run_once()

    task = client.get(f"/api/v1/tasks/{task_id}").json()["data"]
    logs = client.get(f"/api/v1/tasks/{task_id}/logs").json()["data"]
    audits = client.get("/api/v1/audits").json()["data"]
    rendered = json.dumps({"task": task, "logs": logs, "audits": audits})
    for secret in (
        "mock-host-ok",
        "hunter2",
        "raw-token",
        "raw-secret",
        "10.2.3.4",
        "services.sh start",
        '"requested_by": "admin"',
    ):
        assert secret not in rendered
    assert task["targets"][0]["host_name"].startswith("host-")
    assert task["requested_by"].startswith("account-")
    assert "[REDACTED" in rendered


def test_audit_log_is_append_only_in_application_session(db: Session) -> None:
    audit = AuditLog(
        event_type="APPEND_ONLY_TEST",
        actor="test",
        message="created",
        details={},
        created_at=utc_now(),
    )
    db.add(audit)
    db.commit()
    audit.message = "mutated"
    try:
        with pytest.raises(ValueError, match="append-only"):
            db.commit()
    finally:
        db.rollback()
    db.delete(audit)
    try:
        with pytest.raises(ValueError, match="append-only"):
            db.commit()
    finally:
        db.rollback()
