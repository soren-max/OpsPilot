from __future__ import annotations

from sqlalchemy import Select, select
from sqlalchemy.orm import Session, selectinload

from app.core.config import Settings, get_settings
from app.core.enums import ApprovalStatus, OperationAction
from app.core.errors import AppError, ConflictError, ForbiddenError, NotFoundError, ValidationError
from app.db.base import utc_now
from app.models import ApprovalRecord, OperationRequest, User
from app.schemas import OperationCreate, OperationRequestCreate
from app.services.audit import write_audit
from app.services.operations import OperationService, configured_legacy_capabilities
from app.services.rbac import get_user_access, require_permission
from app.services.reliability import request_fingerprint, validate_idempotency_key

WRITE_PERMISSIONS = {
    OperationAction.START: "service.start",
    OperationAction.STOP: "service.stop",
}


class ApprovalService:
    def __init__(self, db: Session, settings: Settings | None = None) -> None:
        self.db = db
        self.settings = settings or get_settings()

    def create(
        self,
        body: OperationRequestCreate,
        actor: User,
        request_id: str | None = None,
        idempotency_key: str | None = None,
    ) -> OperationRequest:
        action = body.operation.action
        key = validate_idempotency_key(idempotency_key, required=True)
        fingerprint = request_fingerprint(body.model_dump(mode="json"))
        existing = self.db.scalar(
            self._query().where(
                OperationRequest.requested_by == actor.id,
                OperationRequest.idempotency_key == key,
            )
        )
        if existing is not None:
            if existing.request_fingerprint != fingerprint:
                self._audit_rejection(
                    actor,
                    action,
                    "IDEMPOTENCY_KEY_REUSED",
                    "Idempotency-Key was already used with a different request",
                    request_id,
                    existing.id,
                )
                self.db.commit()
                raise ConflictError(
                    "IDEMPOTENCY_KEY_REUSED",
                    "Idempotency-Key was already used with a different request",
                )
            write_audit(
                self.db,
                "IDEMPOTENT_REPLAY",
                actor.username,
                "Existing operation request returned for idempotent replay",
                details={"operation_request_id": existing.id, "request_id": request_id},
            )
            self.db.commit()
            return existing
        permission = WRITE_PERMISSIONS.get(action)
        if permission is None:
            rejection = ValidationError("Approval requests support only start and stop")
            self._audit_rejection(actor, action, rejection.code, rejection.message, request_id)
            self.db.commit()
            raise rejection
        try:
            require_permission(self.db, actor, "operation.create")
            require_permission(self.db, actor, permission)
            self._validate_write_gate(action)
        except AppError as exc:
            self._audit_rejection(actor, action, exc.code, exc.message, request_id)
            self.db.commit()
            raise

        item = OperationRequest(
            requested_by=actor.id,
            action=action,
            payload=body.operation.model_dump(mode="json"),
            status=ApprovalStatus.PENDING,
            reason=body.reason,
            idempotency_key=key,
            request_fingerprint=fingerprint,
        )
        self.db.add(item)
        self.db.flush()
        write_audit(
            self.db,
            "OPERATION_REQUEST_CREATED",
            actor.username,
            "Write operation request created",
            details={
                "operation_request_id": item.id,
                "action": action.value,
                "status": item.status.value,
                "execution_mode": ("mock" if self.settings.selected_executor == "mock" else "real"),
                "request_id": request_id,
            },
        )
        self.db.commit()
        return item

    def approve(
        self,
        request_id_value: str,
        actor: User,
        comment: str | None,
        request_id: str | None = None,
    ) -> OperationRequest:
        try:
            require_permission(self.db, actor, "operation.approve")
        except AppError as exc:
            self._audit_rejection(actor, None, exc.code, exc.message, request_id)
            self.db.commit()
            raise
        item = self._get(request_id_value)
        try:
            self._require_pending(item)
        except AppError as exc:
            self._audit_rejection(actor, item.action, exc.code, exc.message, request_id, item.id)
            self.db.commit()
            raise
        if (
            item.requested_by == actor.id
            and item.action in WRITE_PERMISSIONS
            and not self.settings.allow_self_approval
        ):
            self._audit_rejection(
                actor,
                item.action,
                "SELF_APPROVAL_FORBIDDEN",
                "Requesters cannot approve their own high-risk operation",
                request_id,
                item.id,
            )
            self.db.commit()
            raise ForbiddenError(
                "SELF_APPROVAL_FORBIDDEN",
                "Requesters cannot approve their own high-risk operation",
            )

        requester = self.db.get(User, item.requested_by)
        if requester is None or not requester.enabled:
            raise ConflictError("REQUESTER_UNAVAILABLE", "Operation requester is unavailable")
        if any(record.approver_id == actor.id for record in item.approval_records):
            raise ConflictError("DUPLICATE_APPROVER", "The same approver cannot approve twice")
        item.approval_records.append(
            ApprovalRecord(
                operation_request_id=item.id,
                approver_id=actor.id,
                decision=ApprovalStatus.APPROVED,
                comment=comment,
                created_at=utc_now(),
            )
        )
        write_audit(
            self.db,
            "OPERATION_REQUEST_APPROVED",
            actor.username,
            "Write operation request approved",
            details={
                "operation_request_id": item.id,
                "action": item.action.value,
                "request_id": request_id,
            },
        )
        if len(item.approval_records) < self.settings.minimum_approvers:
            self.db.commit()
            return self._get(item.id)
        item.status = ApprovalStatus.APPROVED
        try:
            task = OperationService(self.db, self.settings).create(
                OperationCreate.model_validate(item.payload),
                actor=requester,
                request_id=request_id,
                approved_request=item,
                commit=False,
                idempotency_key=f"approval:{item.id}",
            )
            item.task_id = task.id
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return self._get(item.id)

    def reject(
        self,
        request_id_value: str,
        actor: User,
        comment: str | None,
        request_id: str | None = None,
    ) -> OperationRequest:
        try:
            require_permission(self.db, actor, "operation.reject")
        except AppError as exc:
            self._audit_rejection(actor, None, exc.code, exc.message, request_id)
            self.db.commit()
            raise
        item = self._get(request_id_value)
        try:
            self._require_pending(item)
        except AppError as exc:
            self._audit_rejection(actor, item.action, exc.code, exc.message, request_id, item.id)
            self.db.commit()
            raise
        if item.requested_by == actor.id and not self.settings.allow_self_approval:
            self._audit_rejection(
                actor,
                item.action,
                "SELF_REVIEW_FORBIDDEN",
                "Requesters cannot review their own operation",
                request_id,
                item.id,
            )
            self.db.commit()
            raise ForbiddenError(
                "SELF_REVIEW_FORBIDDEN", "Requesters cannot review their own operation"
            )
        item.status = ApprovalStatus.REJECTED
        item.approval_records.append(
            ApprovalRecord(
                operation_request_id=item.id,
                approver_id=actor.id,
                decision=ApprovalStatus.REJECTED,
                comment=comment,
                created_at=utc_now(),
            )
        )
        write_audit(
            self.db,
            "OPERATION_REQUEST_REJECTED",
            actor.username,
            "Write operation request rejected",
            details={"operation_request_id": item.id, "request_id": request_id},
        )
        self.db.commit()
        return self._get(item.id)

    def cancel(
        self,
        request_id_value: str,
        actor: User,
        request_id: str | None = None,
    ) -> OperationRequest:
        item = self._get(request_id_value)
        permissions = get_user_access(self.db, actor.id).permissions
        can_cancel_any = "operation.cancel" in permissions
        if item.requested_by != actor.id and not can_cancel_any:
            self._audit_rejection(
                actor,
                item.action,
                "PERMISSION_DENIED",
                "Cannot cancel another user's request",
                request_id,
                item.id,
            )
            self.db.commit()
            raise ForbiddenError("PERMISSION_DENIED", "Cannot cancel another user's request")
        try:
            self._require_pending(item)
        except AppError as exc:
            self._audit_rejection(actor, item.action, exc.code, exc.message, request_id, item.id)
            self.db.commit()
            raise
        item.status = ApprovalStatus.CANCELLED
        write_audit(
            self.db,
            "OPERATION_REQUEST_CANCELLED",
            actor.username,
            "Write operation request cancelled",
            details={"operation_request_id": item.id, "request_id": request_id},
        )
        self.db.commit()
        return self._get(item.id)

    def get_visible(self, request_id_value: str, actor: User) -> OperationRequest:
        item = self._get(request_id_value)
        permissions = get_user_access(self.db, actor.id).permissions
        if item.requested_by != actor.id and not {
            "operation.approve",
            "operation.reject",
        }.intersection(permissions):
            raise ForbiddenError("PERMISSION_DENIED", "Operation request is not visible")
        return item

    def list_visible(self, actor: User, limit: int = 100) -> list[OperationRequest]:
        permissions = get_user_access(self.db, actor.id).permissions
        query = self._query().order_by(OperationRequest.created_at.desc()).limit(limit)
        if not {"operation.approve", "operation.reject"}.intersection(permissions):
            query = query.where(OperationRequest.requested_by == actor.id)
        return list(self.db.scalars(query))

    def _validate_write_gate(self, action: OperationAction) -> None:
        if not self.settings.write_operations_enabled:
            raise ForbiddenError("WRITE_OPERATION_DISABLED", "Write operations are disabled")
        if action.value not in self.settings.allowed_action_set:
            raise ForbiddenError("ACTION_NOT_ALLOWED", "Action is outside the configured allowlist")
        if action not in configured_legacy_capabilities(self.settings):
            raise ForbiddenError(
                "EXECUTOR_ACTION_UNSUPPORTED",
                "Configured executor does not support this action",
            )

    def _get(self, request_id_value: str) -> OperationRequest:
        item = self.db.scalar(self._query().where(OperationRequest.id == request_id_value))
        if item is None:
            raise NotFoundError("Operation request does not exist")
        return item

    @staticmethod
    def _require_pending(item: OperationRequest) -> None:
        if item.status is not ApprovalStatus.PENDING:
            raise ConflictError(
                "APPROVAL_ALREADY_DECIDED",
                "Operation request is no longer pending",
                {"status": item.status.value},
            )

    @staticmethod
    def _query() -> Select[tuple[OperationRequest]]:
        return select(OperationRequest).options(selectinload(OperationRequest.approval_records))

    def _audit_rejection(
        self,
        actor: User,
        action: OperationAction | None,
        code: str,
        message: str,
        request_id: str | None,
        operation_request_id: str | None = None,
    ) -> None:
        write_audit(
            self.db,
            "OPERATION_REQUEST_DENIED",
            actor.username,
            "Write operation request denied",
            details={
                "operation_request_id": operation_request_id,
                "action": action.value if action else None,
                "error_code": code,
                "rejection_reason": message,
                "request_id": request_id,
            },
        )
