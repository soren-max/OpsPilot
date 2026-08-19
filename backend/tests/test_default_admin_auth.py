from sqlalchemy import select

from app.bootstrap.seed_users import seed_default_admin
from app.core.config import Settings
from app.core.security import hash_password, verify_password
from app.models import Permission, Role, RolePermission, User, UserRole
from app.services.rbac import DEFAULT_PERMISSION_DEFINITIONS


def test_seed_creates_default_admin_once_without_plaintext_password(db) -> None:
    settings = Settings(default_admin_enabled=True)
    created = seed_default_admin(db, settings)
    assert created is not None
    assert created.username == "admin"
    assert created.status == "ACTIVE"
    assert created.password_hash != settings.default_admin_password
    assert verify_password(settings.default_admin_password, created.password_hash)

    first_hash = created.password_hash
    assert seed_default_admin(db, settings) is not None
    users = list(db.scalars(select(User).where(User.username == "admin")))
    assert len(users) == 1
    assert users[0].password_hash == first_hash


def test_seed_does_not_reset_existing_user_password(db) -> None:
    existing = User(
        username="admin",
        display_name="Existing",
        password_hash="600000$00$00",
        enabled=True,
        status="ACTIVE",
    )
    db.add(existing)
    db.commit()
    seed_default_admin(db, Settings(default_admin_enabled=True))
    assert db.scalar(select(User.password_hash).where(User.username == "admin")) == "600000$00$00"


def test_seed_binds_admin_role_to_all_defined_permissions(db) -> None:
    user = seed_default_admin(db, Settings(default_admin_enabled=True))
    assert user is not None
    role = db.scalar(select(Role).where(Role.code == "admin"))
    assert role is not None
    assert db.scalar(
        select(UserRole).where(UserRole.user_id == user.id, UserRole.role_id == role.id)
    )
    codes = set(
        db.scalars(
            select(Permission.code)
            .join(RolePermission, RolePermission.permission_id == Permission.id)
            .where(RolePermission.role_id == role.id)
        )
    )
    assert codes == set(DEFAULT_PERMISSION_DEFINITIONS)
    assert {
        "service.status",
        "service.start",
        "service.stop",
        "operation.create",
        "operation.approve",
        "operation.reject",
        "operation.cancel",
        "task.read",
        "audit.read",
    } <= codes


def test_login_response_and_auth_errors_are_json(client) -> None:
    success = client.post(
        "/api/v1/auth/login", json={"username": "admin", "password": "admin123-test-only"}
    )
    assert success.status_code == 200
    body = success.json()
    assert body["token_type"] == "bearer"
    assert body["user"]["roles"] == ["admin"]
    assert "service.read" in body["user"]["permissions"]

    wrong_password = client.post(
        "/api/v1/auth/login", json={"username": "admin", "password": "wrong"}
    )
    unknown_user = client.post(
        "/api/v1/auth/login", json={"username": "nobody", "password": "wrong"}
    )
    assert wrong_password.status_code == unknown_user.status_code == 401
    assert wrong_password.json()["code"] == unknown_user.json()["code"] == "INVALID_CREDENTIALS"
    assert wrong_password.json()["message"] == unknown_user.json()["message"] == "账号或密码不正确"


def test_disabled_user_returns_json_403(client, db) -> None:
    user = db.scalar(select(User).where(User.username == "admin"))
    assert user is not None
    user.enabled = False
    user.status = "DISABLED"
    db.commit()
    response = client.post(
        "/api/v1/auth/login", json={"username": "admin", "password": "admin123-test-only"}
    )
    assert response.status_code == 403
    assert response.json()["code"] == "ACCOUNT_DISABLED"
    assert response.json()["message"] == "账号已被禁用，请联系系统管理员"


def test_password_change_revokes_existing_jwt(client, db) -> None:
    old_token = client.headers["Authorization"]
    user = db.scalar(select(User).where(User.username == "admin"))
    assert user is not None
    old_version = user.auth_version
    user.password_hash = hash_password("new-admin-password")
    db.commit()
    assert user.auth_version == old_version + 1

    response = client.get("/api/v1/auth/me", headers={"Authorization": old_token})
    assert response.status_code == 401
    assert response.json()["code"] == "TOKEN_REVOKED"


def test_disabling_user_revokes_existing_jwt(client, db) -> None:
    old_token = client.headers["Authorization"]
    user = db.scalar(select(User).where(User.username == "admin"))
    assert user is not None
    old_version = user.auth_version
    user.enabled = False
    user.status = "DISABLED"
    db.commit()
    assert user.auth_version == old_version + 1

    response = client.get("/api/v1/auth/me", headers={"Authorization": old_token})
    assert response.status_code == 401
    assert response.json()["code"] == "TOKEN_REVOKED"


def test_login_failures_are_rate_limited(client) -> None:
    for _ in range(5):
        response = client.post(
            "/api/v1/auth/login",
            json={"username": "rate-limit-target", "password": "wrong"},
        )
        assert response.status_code == 401
    blocked = client.post(
        "/api/v1/auth/login",
        json={"username": "rate-limit-target", "password": "wrong"},
    )
    assert blocked.status_code == 429
    assert blocked.json()["code"] == "LOGIN_RATE_LIMITED"


def test_public_auth_status_never_discloses_target_allowlists(client) -> None:
    response = client.get("/api/v1/auth/status")
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["allowed_hosts"] == []
    assert data["allowed_services"] == []
    assert data["allowed_actions"] == ["status"]
    assert data["write_operations"] is False
    assert data["approval_required_for_write"] is True
