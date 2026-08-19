from fastapi import APIRouter, Depends, Header, Query, Request, status
from sqlalchemy.orm import Session

from app.api.deps import response
from app.api.routes.auth import get_current_user
from app.core.enums import OperationAction, OperationScope
from app.core.errors import AppError, NotFoundError
from app.db.session import get_db
from app.models import Environment, ServiceStatusSnapshot, TaskLog, TopologySyncState, User
from app.repositories.tasks import TaskRepository
from app.schemas import (
    ApprovalDecisionCreate,
    ApprovalRecordRead,
    AuditRead,
    OperationCreate,
    OperationCreated,
    OperationRequestCreate,
    OperationRequestRead,
    ServiceStatusSnapshotRead,
    TargetRead,
    TaskLogRead,
    TaskRead,
    TopologySyncStateRead,
)
from app.services.approvals import ApprovalService
from app.services.audit import write_audit
from app.services.operations import OperationService
from app.services.rbac import require_permission
from app.services.redaction import (
    redact_account,
    redact_details,
    redact_hostname,
    redact_text,
)

router = APIRouter(tags=["operations"])


def require_read_access(db: Session, user: User, permission: str, request: Request) -> None:
    try:
        require_permission(db, user, permission)
    except AppError as rejection:
        write_audit(
            db,
            "READ_ACCESS_DENIED",
            user.username,
            "Protected read operation denied",
            details={
                "permission": permission,
                "error_code": rejection.code,
                "request_id": request.state.request_id,
            },
        )
        db.commit()
        raise


def operation_request_read(db: Session, item: object) -> OperationRequestRead:
    requester = db.get(User, item.requested_by)  # type: ignore[attr-defined]
    return OperationRequestRead(
        id=item.id,  # type: ignore[attr-defined]
        requested_by=redact_account(requester.username if requester else "unknown"),
        action=item.action,  # type: ignore[attr-defined]
        payload=redact_details(item.payload),  # type: ignore[attr-defined]
        status=item.status,  # type: ignore[attr-defined]
        task_id=item.task_id,  # type: ignore[attr-defined]
        reason=item.reason,  # type: ignore[attr-defined]
        created_at=item.created_at,  # type: ignore[attr-defined]
        updated_at=item.updated_at,  # type: ignore[attr-defined]
        approvals=[
            ApprovalRecordRead.model_validate(record)
            for record in item.approval_records  # type: ignore[attr-defined]
        ],
    )


def task_read(db: Session, task: object, include_targets: bool = True) -> TaskRead:
    environment = db.get(Environment, task.environment_id)  # type: ignore[attr-defined]
    targets = []
    if include_targets:
        targets = [
            TargetRead(
                id=item.id,
                service_id=item.service_id,
                host_id=item.host_id,
                service_name=item.service.name,
                host_name=redact_hostname(item.host.name),
                status=item.status,
                output=redact_text(item.output, hostnames=(item.host.name,)),
                error_message=redact_text(item.error_message, hostnames=(item.host.name,)),
                duration_ms=item.duration_ms,
                attempt_count=item.attempt_count,
                verification_status=item.verification_status,
                verification_output=redact_text(
                    item.verification_output, hostnames=(item.host.name,)
                ),
            )
            for item in task.targets  # type: ignore[attr-defined]
        ]
    return TaskRead(
        id=task.id,  # type: ignore[attr-defined]
        environment_id=task.environment_id,  # type: ignore[attr-defined]
        environment_name=environment.name if environment else "Unknown",
        action=task.action,  # type: ignore[attr-defined]
        scope=task.scope,  # type: ignore[attr-defined]
        status=task.status,  # type: ignore[attr-defined]
        requested_by=redact_account(task.requested_by),  # type: ignore[attr-defined]
        created_at=task.created_at,  # type: ignore[attr-defined]
        started_at=task.started_at,  # type: ignore[attr-defined]
        finished_at=task.finished_at,  # type: ignore[attr-defined]
        error_message=task.error_message,  # type: ignore[attr-defined]
        targets=targets,
    )


@router.post("/operations", status_code=status.HTTP_202_ACCEPTED)
def create_operation(
    payload: OperationCreate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict[str, object]:
    task = OperationService(db).create(
        payload,
        actor=user,
        request_id=request.state.request_id,
        idempotency_key=idempotency_key,
    )
    return response(request, OperationCreated(task_id=task.id, status=task.status))


@router.post("/operation-requests", status_code=status.HTTP_201_CREATED)
def create_operation_request(
    body: OperationRequestCreate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict[str, object]:
    item = ApprovalService(db).create(
        body, user, request.state.request_id, idempotency_key=idempotency_key
    )
    return response(request, operation_request_read(db, item))


@router.get("/operation-requests")
def operation_requests(
    request: Request,
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, object]:
    items = ApprovalService(db).list_visible(user, limit)
    return response(request, [operation_request_read(db, item) for item in items])


@router.get("/operation-requests/{operation_request_id}")
def operation_request_detail(
    operation_request_id: str,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, object]:
    item = ApprovalService(db).get_visible(operation_request_id, user)
    return response(request, operation_request_read(db, item))


@router.post("/operation-requests/{operation_request_id}/approve")
def approve_operation_request(
    operation_request_id: str,
    body: ApprovalDecisionCreate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, object]:
    item = ApprovalService(db).approve(
        operation_request_id, user, body.comment, request.state.request_id
    )
    return response(request, operation_request_read(db, item))


@router.post("/operation-requests/{operation_request_id}/reject")
def reject_operation_request(
    operation_request_id: str,
    body: ApprovalDecisionCreate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, object]:
    item = ApprovalService(db).reject(
        operation_request_id, user, body.comment, request.state.request_id
    )
    return response(request, operation_request_read(db, item))


@router.post("/operation-requests/{operation_request_id}/cancel")
def cancel_operation_request(
    operation_request_id: str,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, object]:
    item = ApprovalService(db).cancel(operation_request_id, user, request.state.request_id)
    return response(request, operation_request_read(db, item))


@router.post("/topology-sync", status_code=status.HTTP_202_ACCEPTED)
def create_topology_sync(
    environment_id: str,
    request: Request,
    requested_by: str = "web-user",
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, object]:
    task = OperationService(db).create(
        OperationCreate(
            environment_id=environment_id,
            action=OperationAction.DISCOVER_TOPOLOGY,
            scope=OperationScope.ALL,
            requested_by=requested_by,
        ),
        actor=user,
        request_id=request.state.request_id,
    )
    return response(request, OperationCreated(task_id=task.id, status=task.status))


@router.get("/tasks")
def tasks(
    request: Request,
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, object]:
    require_read_access(db, user, "task.read", request)
    return response(
        request,
        [
            task_read(db, item, include_targets=True)
            for item in TaskRepository(db).list_tasks(limit)
        ],
    )


@router.get("/tasks/{task_id}")
def task_detail(
    task_id: str,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, object]:
    require_read_access(db, user, "task.read", request)
    item = TaskRepository(db).get(task_id)
    if item is None:
        raise NotFoundError("Task does not exist")
    return response(request, task_read(db, item))


@router.post("/tasks/{task_id}/cancel")
def cancel_task(
    task_id: str,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, object]:
    item = OperationService(db).cancel(task_id, user, request.state.request_id)
    return response(request, task_read(db, item))


@router.get("/audits")
def audits(
    request: Request,
    limit: int = Query(default=200, ge=1, le=500),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, object]:
    require_read_access(db, user, "audit.read", request)
    items = [
        AuditRead(
            id=item.id,
            task_id=item.task_id,
            event_type=item.event_type,
            actor=redact_account(item.actor),
            message=redact_text(item.message) or "",
            details=redact_details(item.details),
            created_at=item.created_at,
        )
        for item in TaskRepository(db).list_audits(limit)
    ]
    return response(request, items)


@router.get("/tasks/{task_id}/logs")
def task_logs(
    task_id: str,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, object]:
    require_read_access(db, user, "task.read", request)
    task = TaskRepository(db).get(task_id)
    if task is None:
        raise NotFoundError("Task does not exist")
    hostnames = tuple(target.host.name for target in task.targets)
    items = db.query(TaskLog).filter(TaskLog.task_id == task_id).order_by(TaskLog.created_at).all()
    return response(
        request,
        [
            TaskLogRead(
                id=item.id,
                task_id=item.task_id,
                target_id=item.target_id,
                stream=item.stream,
                message=redact_text(item.message, hostnames=hostnames) or "",
                exit_code=item.exit_code,
                dry_run=item.dry_run,
                created_at=item.created_at,
            )
            for item in items
        ],
    )


@router.get("/status-snapshots")
def status_snapshots(
    request: Request,
    environment_id: str = Query(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, object]:
    require_read_access(db, user, "task.read", request)
    items = (
        db.query(ServiceStatusSnapshot)
        .filter(ServiceStatusSnapshot.environment_id == environment_id)
        .order_by(ServiceStatusSnapshot.observed_at.desc())
        .all()
    )
    return response(request, [ServiceStatusSnapshotRead.model_validate(item) for item in items])


@router.get("/topology-sync/{environment_id}")
def topology_sync_state(
    environment_id: str,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, object]:
    require_read_access(db, user, "task.read", request)
    item = db.get(TopologySyncState, environment_id)
    if item is None:
        raise NotFoundError("Topology sync state does not exist")
    return response(request, TopologySyncStateRead.model_validate(item))
