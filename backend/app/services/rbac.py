"""RBAC queries and permission checks shared by API and service layers."""

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.models import Permission, Role, RolePermission, User, UserRole

DEFAULT_PERMISSION_DEFINITIONS: dict[str, str] = {
    "service.read": "Read service inventory and health",
    "service.status": "Run service status operations",
    "service.start": "Request service start operations",
    "service.stop": "Request service stop operations",
    "host.read": "Read host inventory and state",
    "task.read": "Read operation tasks",
    "task.cancel": "Cancel pending operation tasks",
    "audit.read": "Read audit logs",
    "access.read": "Read local RBAC configuration",
    "operation.create": "Create controlled operation requests",
    "operation.request": "Legacy alias for operation.create",
    "operation.approve": "Approve controlled operation requests",
    "operation.reject": "Reject controlled operation requests",
    "operation.cancel": "Cancel controlled operation requests",
    "config.read": "Read operations integration configuration",
    "config.write": "Create and update operations integration configuration",
    "config.test": "Run read-only operations integration tests",
    "incident.read": "Read incidents and timelines",
    "incident.write": "Create incidents, evidence, hypotheses, and diagnoses",
    "incident.resolve": "Resolve investigated incidents",
    "incident.close": "Close resolved incidents",
    "incident.knowledge.read": "Read resolved incident knowledge projections",
}


@dataclass(frozen=True)
class UserAccess:
    roles: list[str]
    permissions: list[str]


def get_user_access(db: Session, user_id: str) -> UserAccess:
    role_codes = list(
        db.scalars(
            select(Role.code)
            .join(UserRole, UserRole.role_id == Role.id)
            .where(UserRole.user_id == user_id)
            .order_by(Role.code)
        )
    )
    permission_codes = list(
        db.scalars(
            select(Permission.code)
            .join(RolePermission, RolePermission.permission_id == Permission.id)
            .join(UserRole, UserRole.role_id == RolePermission.role_id)
            .where(UserRole.user_id == user_id)
            .distinct()
            .order_by(Permission.code)
        )
    )
    return UserAccess(roles=role_codes, permissions=permission_codes)


def require_permission(db: Session, user: User, permission: str) -> None:
    if permission not in set(get_user_access(db, user.id).permissions):
        raise AppError(403, "PERMISSION_DENIED", "当前账号没有执行此操作的权限")
