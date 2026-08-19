from sqlalchemy import and_, delete, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.enums import (
    ApprovalStatus,
    OperationAction,
    OperationScope,
    PartialFailurePolicy,
    TargetStatus,
    TaskStatus,
)
from app.core.errors import AppError, ConflictError, ForbiddenError, NotFoundError, ValidationError
from app.db.base import utc_now
from app.domain.actions.models import (
    ActionRequest,
    ActionType,
    ServiceActionParams,
    TargetEnvironment,
)
from app.domain.actions.policy import ActionPolicyEngine
from app.models import (
    OperationLock,
    OperationRequest,
    OperationTarget,
    OperationTask,
    ServiceDeployment,
    User,
)
from app.repositories.catalog import CatalogRepository
from app.repositories.tasks import TaskRepository
from app.schemas import OperationCreate
from app.services.audit import write_audit
from app.services.execution_policy import WRITE_ACTIONS
from app.services.rbac import require_permission
from app.services.reliability import request_fingerprint, validate_idempotency_key

STATUS_ACTIONS = frozenset(
    {
        OperationAction.STATUS,
        OperationAction.STATUS_ALL,
        OperationAction.STATUS_SERVICE,
        OperationAction.STATUS_SERVICE_HOSTS,
    }
)


def structured_action(
    *,
    action: OperationAction,
    target: str,
    service: str,
    environment_level: object,
) -> ActionRequest:
    if action in STATUS_ACTIONS:
        action_type = ActionType.GET_SERVICE_STATUS
    elif action is OperationAction.RESTART:
        action_type = ActionType.RESTART_SERVICE
    else:
        raise ValidationError(
            "Operation is not part of the portable action boundary",
            {"action": action.value, "allowed_actions": ["status", "restart"]},
        )
    return ActionRequest(
        action_type=action_type,
        target=target,
        environment=TargetEnvironment(str(environment_level).lower()),
        parameters=ServiceActionParams(service=service),
        reason=f"Execute approved {action_type.value} operation.",
    )


class OperationService:
    def __init__(self, db: Session, settings: Settings | None = None) -> None:
        self.db = db
        self.settings = settings or get_settings()
        self.catalog = CatalogRepository(db)
        self.tasks = TaskRepository(db)

    def cancel(self, task_id: str, actor: User, request_id: str | None = None) -> OperationTask:
        try:
            require_permission(self.db, actor, "task.cancel")
        except AppError as rejection:
            write_audit(
                self.db,
                "TASK_CANCEL_DENIED",
                actor.username,
                "Task cancellation denied",
                task_id,
                {"error_code": rejection.code, "request_id": request_id},
            )
            self.db.commit()
            raise
        task = self.tasks.get(task_id)
        if task is None:
            raise NotFoundError("Task does not exist")
        if task.status not in {TaskStatus.PENDING, TaskStatus.RUNNING}:
            write_audit(
                self.db,
                "TASK_CANCEL_DENIED",
                actor.username,
                "Terminal task cannot be cancelled",
                task.id,
                {"error_code": "TASK_NOT_CANCELLABLE", "request_id": request_id},
            )
            self.db.commit()
            raise ConflictError("TASK_NOT_CANCELLABLE", "Task is already terminal")
        task.cancel_requested = True
        if task.status is TaskStatus.PENDING:
            task.status = TaskStatus.CANCELLED
            task.finished_at = utc_now()
            for target in task.targets:
                target.status = TargetStatus.CANCELLED
                target.error_message = "TASK_CANCELLED"
            self.db.execute(delete(OperationLock).where(OperationLock.task_id == task.id))
        write_audit(
            self.db,
            "TASK_CANCEL_REQUESTED",
            actor.username,
            "Task cancellation requested",
            task.id,
            {"status": task.status.value, "request_id": request_id},
        )
        self.db.commit()
        return task

    def create(
        self,
        payload: OperationCreate,
        actor: User | None = None,
        request_id: str | None = None,
        approved_request: OperationRequest | None = None,
        commit: bool = True,
        idempotency_key: str | None = None,
    ) -> OperationTask:
        """Create a task after service-layer RBAC and safety configuration checks."""
        approval_granted = (
            approved_request is not None
            and approved_request.status is ApprovalStatus.APPROVED
            and approved_request.action is payload.action
        )
        if approved_request is not None and not approval_granted:
            raise ForbiddenError(
                "APPROVAL_INVALID",
                "Operation request is not approved for this action",
                {"action": payload.action.value},
            )
        if actor is not None:
            required_permission = {
                OperationAction.START: "service.start",
                OperationAction.STOP: "service.stop",
                OperationAction.RESTART: "service.start",
                OperationAction.DEPLOY: "service.start",
            }.get(payload.action, "service.status")
            try:
                require_permission(self.db, actor, required_permission)
            except AppError as rejection:
                rejected_environment = self.catalog.get_environment(payload.environment_id)
                rejected_service = (
                    self.catalog.get_service(payload.service_id) if payload.service_id else None
                )
                rejected_hosts = [
                    item.name
                    for host_id in ([payload.host_id] if payload.host_id else payload.host_ids)
                    if (item := self.catalog.get_host(host_id)) is not None
                ]
                write_audit(
                    self.db,
                    "EXECUTION_REJECTED",
                    actor.username,
                    "Operation rejected by user permission policy",
                    details={
                        "action": payload.action.value,
                        "environment": (
                            rejected_environment.code
                            if rejected_environment is not None
                            else payload.environment_id
                        ),
                        "hosts": rejected_hosts,
                        "service": (
                            rejected_service.name
                            if rejected_service is not None
                            else payload.service_id
                        ),
                        "error_code": rejection.code,
                        "rejection_reason": rejection.message,
                        "request_id": request_id,
                    },
                )
                if commit:
                    self.db.commit()
                else:
                    self.db.flush()
                raise ForbiddenError(
                    rejection.code,
                    rejection.message,
                    {
                        "action": payload.action.value,
                        "environment": (
                            rejected_environment.code
                            if rejected_environment is not None
                            else payload.environment_id
                        ),
                        "hosts": rejected_hosts,
                        "service": (
                            rejected_service.name
                            if rejected_service is not None
                            else payload.service_id
                        ),
                        "rejection_reason": rejection.message,
                    },
                ) from rejection
        actor_name = actor.username if actor is not None else payload.requested_by
        key = validate_idempotency_key(
            idempotency_key,
            required=(
                payload.action in WRITE_ACTIONS and approved_request is None and actor is not None
            ),
        )
        fingerprint = request_fingerprint(payload.model_dump(mode="json"))
        if key:
            existing = self.db.scalar(
                select(OperationTask).where(
                    OperationTask.requested_by == actor_name,
                    OperationTask.idempotency_key == key,
                )
            )
            if existing is not None:
                if existing.request_fingerprint != fingerprint:
                    write_audit(
                        self.db,
                        "EXECUTION_REJECTED",
                        actor_name,
                        "Idempotency-Key reused with a different operation",
                        details={
                            "error_code": "IDEMPOTENCY_KEY_REUSED",
                            "request_id": request_id,
                        },
                    )
                    if commit:
                        self.db.commit()
                    else:
                        self.db.flush()
                    raise ConflictError(
                        "IDEMPOTENCY_KEY_REUSED",
                        "Idempotency-Key was already used with a different operation",
                    )
                write_audit(
                    self.db,
                    "IDEMPOTENT_REPLAY",
                    actor_name,
                    "Existing task returned for idempotent replay",
                    existing.id,
                    {"request_id": request_id},
                )
                if commit:
                    self.db.commit()
                else:
                    self.db.flush()
                return existing
        environment = self.catalog.get_environment(payload.environment_id)
        if environment is None:
            raise NotFoundError("Environment does not exist")
        if not environment.enabled:
            raise ValidationError("Environment is disabled")
        query = self.catalog.deployments_query(payload.environment_id)
        service = None
        host = None

        if payload.service_id:
            service = self.catalog.get_service(payload.service_id)
            if service is None:
                raise NotFoundError("Service does not exist")
            if service.environment_id != payload.environment_id:
                raise ValidationError("Service does not belong to the environment")
        if payload.host_id:
            host = self.catalog.get_host(payload.host_id)
            if host is None:
                raise NotFoundError("Host does not exist")
            if host.environment_id != payload.environment_id:
                raise ValidationError("Host does not belong to the environment")

        if payload.scope is OperationScope.ALL:
            if payload.service_id or payload.host_id or payload.host_ids:
                raise ValidationError("all scope does not accept target identifiers")
        elif payload.scope is OperationScope.SERVICE:
            if service is None or payload.host_id or payload.host_ids:
                raise ValidationError("service scope requires only service_id")
            query = query.where(ServiceDeployment.service_id == service.id)
        elif payload.scope is OperationScope.SERVICE_HOSTS:
            if service is None or not payload.host_ids or payload.host_id:
                raise ValidationError("service_hosts requires service_id and host_ids")
            query = query.where(
                ServiceDeployment.service_id == service.id,
                ServiceDeployment.host_id.in_(payload.host_ids),
            )
        elif payload.scope is OperationScope.HOST:
            if host is None or payload.service_id or payload.host_ids:
                raise ValidationError("host scope requires only host_id")
            query = query.where(ServiceDeployment.host_id == host.id)
        elif payload.scope is OperationScope.HOSTS:
            if not payload.host_ids or payload.service_id or payload.host_id:
                raise ValidationError("hosts scope requires only host_ids")
            query = query.where(ServiceDeployment.host_id.in_(payload.host_ids))

        deployments = list(self.db.scalars(query))
        requested_host_ids = set(payload.host_ids)
        if requested_host_ids:
            found_host_ids = {deployment.host_id for deployment in deployments}
            missing = requested_host_ids - found_host_ids
            if missing:
                raise ValidationError(
                    "One or more hosts are invalid for this environment/service",
                    {"invalid_host_ids": sorted(missing)},
                )
        if not deployments:
            raise ValidationError("No enabled deployments match the requested scope")
        policy = ActionPolicyEngine(frozenset(item.host.name for item in deployments))
        for deployment in deployments:
            action = structured_action(
                action=payload.action,
                target=deployment.host.name,
                service=deployment.service.name,
                environment_level=environment.environment_level.value,
            )
            assessment = policy.assess(action, approval_granted=approval_granted)
            if not assessment.allowed:
                actor_name = actor.username if actor is not None else payload.requested_by
                write_audit(
                    self.db,
                    "EXECUTION_REJECTED",
                    actor_name,
                    "Operation rejected by portable action policy",
                    details={
                        "action": payload.action.value,
                        "environment": environment.code,
                        "host": deployment.host.name,
                        "service": deployment.service.name,
                        "error_code": "ACTION_POLICY_REJECTED",
                        "rejection_reason": assessment.reason,
                        "policy_rule": assessment.policy_rule,
                        "request_id": request_id,
                    },
                )
                if commit:
                    self.db.commit()
                else:
                    self.db.flush()
                raise ForbiddenError(
                    "ACTION_POLICY_REJECTED",
                    assessment.reason,
                    {
                        "action": payload.action.value,
                        "environment": environment.code,
                        "host": deployment.host.name,
                        "service": deployment.service.name,
                        "rejection_reason": assessment.reason,
                        "policy_rule": assessment.policy_rule,
                    },
                )

        if payload.action in WRITE_ACTIONS:
            lock_conditions = [
                and_(
                    OperationLock.environment_id == environment.id,
                    OperationLock.service_id == item.service_id,
                    OperationLock.host_id == item.host_id,
                )
                for item in deployments
            ]
            conflicting_lock = self.db.scalar(
                select(OperationLock).where(or_(*lock_conditions)).limit(1)
            )
            if conflicting_lock is not None:
                write_audit(
                    self.db,
                    "EXECUTION_REJECTED",
                    actor_name,
                    "Operation target is locked by another task",
                    details={
                        "error_code": "TARGET_LOCK_CONFLICT",
                        "conflicting_task_id": conflicting_lock.task_id,
                        "request_id": request_id,
                    },
                )
                if commit:
                    self.db.commit()
                else:
                    self.db.flush()
                raise ConflictError(
                    "TARGET_LOCK_CONFLICT",
                    "One or more operation targets are locked by another task",
                    {"conflicting_task_id": conflicting_lock.task_id},
                )

        task = OperationTask(
            environment_id=environment.id,
            action=payload.action,
            scope=payload.scope,
            status=TaskStatus.PENDING,
            requested_by=actor_name,
            parameters={},
            operation_request_id=(approved_request.id if approved_request else None),
            idempotency_key=key,
            request_fingerprint=fingerprint,
            partial_failure_policy=(
                payload.partial_failure_policy
                or PartialFailurePolicy(self.settings.partial_failure_policy)
            ),
            targets=[
                OperationTarget(service_id=item.service_id, host_id=item.host_id)
                for item in deployments
            ],
        )
        try:
            self.tasks.add(task)
        except IntegrityError as exc:
            self.db.rollback()
            existing = (
                self.db.scalar(
                    select(OperationTask).where(
                        OperationTask.requested_by == actor_name,
                        OperationTask.idempotency_key == key,
                    )
                )
                if key
                else None
            )
            write_audit(
                self.db,
                "EXECUTION_REJECTED",
                actor_name,
                "Concurrent duplicate request rejected",
                details={"error_code": "DUPLICATE_REQUEST", "request_id": request_id},
            )
            self.db.commit()
            if existing is not None and existing.request_fingerprint == fingerprint:
                return existing
            raise ConflictError(
                "DUPLICATE_REQUEST", "A duplicate operation request already exists"
            ) from exc
        if payload.action in WRITE_ACTIONS:
            self.db.add_all(
                [
                    OperationLock(
                        environment_id=environment.id,
                        service_id=item.service_id,
                        host_id=item.host_id,
                        task_id=task.id,
                        acquired_at=utc_now(),
                    )
                    for item in deployments
                ]
            )
            try:
                self.db.flush()
            except IntegrityError as exc:
                self.db.rollback()
                write_audit(
                    self.db,
                    "EXECUTION_REJECTED",
                    actor_name,
                    "Concurrent operation target lock conflict",
                    details={
                        "error_code": "TARGET_LOCK_CONFLICT",
                        "request_id": request_id,
                    },
                )
                self.db.commit()
                raise ConflictError(
                    "TARGET_LOCK_CONFLICT",
                    "One or more operation targets are locked by another task",
                ) from exc
        write_audit(
            self.db,
            "TASK_CREATED",
            task.requested_by,
            "Operation task created",
            task.id,
            {
                "action": task.action.value,
                "scope": task.scope.value,
                "target_count": len(deployments),
                "environment": environment.code,
                "requested_by": task.requested_by,
                "targets": [
                    {"service": item.service.name, "host": item.host.name} for item in deployments
                ],
                "request_id": request_id,
            },
        )
        if commit:
            self.db.commit()
        else:
            self.db.flush()
        return task
