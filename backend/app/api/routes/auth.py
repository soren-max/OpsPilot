"""Authentication endpoints for the local, dry-run console."""

import threading
import time
from collections import defaultdict, deque

from fastapi import APIRouter, Depends, Header, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import response
from app.core.config import get_settings
from app.core.errors import AppError
from app.core.security import create_token, decode_token, verify_password
from app.db.session import get_db
from app.models import User
from app.services.rbac import get_user_access

router = APIRouter(tags=["auth"])


class LoginFailureLimiter:
    """Small in-process limiter; avoids adding a network dependency to local auth."""

    def __init__(self) -> None:
        self._failures: dict[str, deque[float]] = defaultdict(deque)
        self._blocked_until: dict[str, float] = {}
        self._lock = threading.Lock()

    def check(self, key: str) -> None:
        now = time.monotonic()
        with self._lock:
            if self._blocked_until.get(key, 0) > now:
                raise AppError(429, "LOGIN_RATE_LIMITED", "登录失败次数过多，请稍后重试")
            self._blocked_until.pop(key, None)

    def failure(self, key: str) -> None:
        settings = get_settings()
        now = time.monotonic()
        cutoff = now - settings.login_failure_window_seconds
        with self._lock:
            failures = self._failures[key]
            while failures and failures[0] < cutoff:
                failures.popleft()
            failures.append(now)
            if len(failures) >= settings.login_failure_limit:
                self._blocked_until[key] = now + settings.login_lockout_seconds
                failures.clear()

    def success(self, key: str) -> None:
        with self._lock:
            self._failures.pop(key, None)
            self._blocked_until.pop(key, None)


login_failure_limiter = LoginFailureLimiter()


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=80)
    password: str = Field(min_length=1, max_length=256)


class UserInfo(BaseModel):
    id: str
    username: str
    display_name: str
    status: str
    roles: list[str]
    permissions: list[str]


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserInfo


def _get_token(authorization: str = Header(default="")) -> str:
    return authorization.removeprefix("Bearer ") if authorization.startswith("Bearer ") else ""


def user_info(db: Session, user: User) -> UserInfo:
    access = get_user_access(db, user.id)
    return UserInfo(
        id=user.id,
        username=user.username,
        display_name=user.display_name,
        status="ACTIVE" if user.enabled and user.status == "ACTIVE" else "DISABLED",
        roles=access.roles,
        permissions=access.permissions,
    )


def get_current_user(
    request: Request,
    token: str = Depends(_get_token),
    db: Session = Depends(get_db),
) -> User:
    """Extract a bearer token and return an active local user."""
    if not token:
        raise AppError(401, "UNAUTHORIZED", "未登录或登录已过期")
    payload = decode_token(token)
    if payload is None:
        raise AppError(401, "TOKEN_INVALID", "登录已过期，请重新登录")
    user_id = payload.get("sub")
    if not isinstance(user_id, str):
        raise AppError(401, "TOKEN_INVALID", "登录已过期，请重新登录")
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise AppError(401, "UNAUTHORIZED", "未登录或登录已过期")
    if payload.get("auth_version") != user.auth_version:
        raise AppError(401, "TOKEN_REVOKED", "登录凭据已失效，请重新登录")
    if not user.enabled or user.status != "ACTIVE":
        raise AppError(403, "ACCOUNT_DISABLED", "账号已被禁用，请联系系统管理员")
    request.state.actor = user.username
    return user


def get_optional_current_user(
    request: Request,
    token: str = Depends(_get_token),
    db: Session = Depends(get_db),
) -> User | None:
    """Return an active token user without making the login-screen endpoint private."""
    if not token:
        return None
    payload = decode_token(token)
    if payload is None:
        return None
    user_id = payload.get("sub")
    if not isinstance(user_id, str):
        return None
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        return None
    if payload.get("auth_version") != user.auth_version:
        return None
    if not user.enabled or user.status != "ACTIVE":
        return None
    request.state.actor = user.username
    return user


@router.get("/auth/status")
def auth_status(
    request: Request,
    db: Session = Depends(get_db),
    user: User | None = Depends(get_optional_current_user),
) -> dict[str, object]:
    """Return the public local security context."""
    settings = get_settings()
    access = get_user_access(db, user.id) if user is not None else None
    permissions = set(access.permissions) if access else set()
    capabilities = {
        "observe": "service.status" in permissions,
        "remediate": "service.start" in permissions,
        "approve": "operation.approve" in permissions,
        "administer": "config.write" in permissions,
    }
    return response(
        request,
        {
            "environment": settings.environment,
            "environment_mode": settings.environment_mode,
            "executor": settings.selected_executor,
            "execution_mode": "mock" if settings.selected_executor == "mock" else "real",
            "write_operations": settings.write_operations_enabled,
            "production_operations": settings.production_operations_enabled,
            "approval_required_for_write": settings.approval_required_for_write,
            "safe_mode": settings.dry_run_only or not settings.write_operations_enabled,
            "real_execution": settings.selected_executor == "ansible",
            # This endpoint is intentionally public for the login screen. Target
            # allowlists are enforcement inputs and must never be disclosed here.
            "allowed_hosts": [],
            "allowed_services": [],
            # The backend remains authoritative for target, action, RBAC and
            # approval checks. This public response intentionally omits targets.
            "allowed_actions": [
                action
                for action, available in (
                    ("status", capabilities["observe"]),
                    ("restart", capabilities["remediate"]),
                )
                if available
            ],
            "permissions": sorted(permissions),
            "approval": {
                "required_for_write": settings.approval_required_for_write,
                "allow_self_approval": settings.allow_self_approval,
                "minimum_approvers": settings.minimum_approvers,
                "can_request": "operation.create" in permissions,
                "can_approve": "operation.approve" in permissions,
                "can_reject": "operation.reject" in permissions,
                "can_cancel": "operation.cancel" in permissions,
            },
            "capabilities": capabilities,
            "executor_capabilities": {
                "status": True,
                "restart": True,
            },
        },
    )


@router.post("/auth/login", response_model=LoginResponse)
def login(body: LoginRequest, request: Request, db: Session = Depends(get_db)) -> LoginResponse:
    """Return a direct JSON login response, never an empty success body."""
    client_host = request.client.host if request.client else "unknown"
    limiter_key = f"{client_host}:{body.username.casefold()}"
    login_failure_limiter.check(limiter_key)
    user = db.query(User).filter(User.username == body.username).first()
    if user is None or not verify_password(body.password, user.password_hash):
        login_failure_limiter.failure(limiter_key)
        raise AppError(401, "INVALID_CREDENTIALS", "账号或密码不正确")
    if not user.enabled or user.status != "ACTIVE":
        login_failure_limiter.failure(limiter_key)
        raise AppError(403, "ACCOUNT_DISABLED", "账号已被禁用，请联系系统管理员")
    login_failure_limiter.success(limiter_key)
    return LoginResponse(
        access_token=create_token(user.id, user.auth_version), user=user_info(db, user)
    )


@router.post("/auth/logout")
def logout(request: Request) -> dict[str, object]:
    return response(request, {"message": "已退出登录"})


@router.get("/auth/me", response_model=UserInfo)
def me(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> UserInfo:
    return user_info(db, user)
