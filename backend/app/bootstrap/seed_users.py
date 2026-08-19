"""Idempotent local user and RBAC seed data."""

import logging

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.security import hash_password
from app.models import Permission, Role, RolePermission, User, UserRole
from app.services.rbac import DEFAULT_PERMISSION_DEFINITIONS

logger = logging.getLogger(__name__)


def _get_or_create_permission(db: Session, code: str, description: str) -> Permission:
    permission = db.scalar(select(Permission).where(Permission.code == code))
    if permission is not None:
        return permission
    try:
        with db.begin_nested():
            permission = Permission(code=code, description=description)
            db.add(permission)
            db.flush()
    except IntegrityError:
        permission = db.scalar(select(Permission).where(Permission.code == code))
    if permission is None:
        raise RuntimeError(f"Could not create permission {code}")
    return permission


def _get_or_create_admin_role(db: Session) -> Role:
    role = db.scalar(select(Role).where(Role.code == "admin"))
    if role is not None:
        return role
    try:
        with db.begin_nested():
            role = Role(code="admin", name="系统管理员", description="本地控制台管理员")
            db.add(role)
            db.flush()
    except IntegrityError:
        role = db.scalar(select(Role).where(Role.code == "admin"))
    if role is None:
        raise RuntimeError("Could not create admin role")
    return role


def _ensure_role_permission(db: Session, role_id: str, permission_id: str) -> None:
    exists = db.scalar(
        select(RolePermission.role_id).where(
            RolePermission.role_id == role_id, RolePermission.permission_id == permission_id
        )
    )
    if exists is not None:
        return
    try:
        with db.begin_nested():
            db.add(RolePermission(role_id=role_id, permission_id=permission_id))
            db.flush()
    except IntegrityError:
        return


def _ensure_user_role(db: Session, user_id: str, role_id: str) -> None:
    exists = db.scalar(
        select(UserRole.user_id).where(UserRole.user_id == user_id, UserRole.role_id == role_id)
    )
    if exists is not None:
        return
    try:
        with db.begin_nested():
            db.add(UserRole(user_id=user_id, role_id=role_id))
            db.flush()
    except IntegrityError:
        return


def seed_default_admin(db: Session, settings: Settings) -> User | None:
    """Create local admin once, without overwriting existing credentials."""
    permissions: dict[str, Permission] = {}
    for code, description in DEFAULT_PERMISSION_DEFINITIONS.items():
        permissions[code] = _get_or_create_permission(db, code, description)

    role = _get_or_create_admin_role(db)
    for permission in permissions.values():
        _ensure_role_permission(db, role.id, permission.id)

    if not settings.default_admin_enabled:
        db.commit()
        return None

    user = db.scalar(select(User).where(User.username == settings.default_admin_username))
    if user is None:
        try:
            with db.begin_nested():
                user = User(
                    username=settings.default_admin_username,
                    display_name="系统管理员",
                    password_hash=hash_password(settings.default_admin_password),
                    enabled=True,
                    status="ACTIVE",
                )
                db.add(user)
                db.flush()
                logger.info("Created configured local default administrator account")
        except IntegrityError:
            user = db.scalar(select(User).where(User.username == settings.default_admin_username))
    if user is None:
        raise RuntimeError("Could not create configured default administrator")
    # Preserve credentials and activation state, but normalize the local demo
    # account label so the console header consistently identifies the role.
    if user.display_name != "系统管理员":
        user.display_name = "系统管理员"

    _ensure_user_role(db, user.id, role.id)
    db.commit()
    return user
