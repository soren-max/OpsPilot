from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import response
from app.api.routes.auth import get_current_user
from app.core.config import get_settings
from app.core.enums import IntegrationConfigStatus
from app.core.errors import AppError, NotFoundError
from app.db.session import get_db
from app.integration_schemas import CredentialCreate, IntegrationConfigInput
from app.models import (
    Environment,
    Host,
    OperationsIntegrationConfig,
    Service,
    ServiceDeployment,
    User,
)
from app.services.audit import write_audit
from app.services.integration_config import (
    all_configured_tests_passed,
    list_credentials,
    read_config,
    save_config,
    serialize_config,
    store_credential,
    test_ssh,
    test_status,
    validate_config,
)
from app.services.rbac import require_permission

router = APIRouter(prefix="/admin/operations-integration", tags=["operations-integration"])


def _config_or_404(db: Session, environment_id: str) -> OperationsIntegrationConfig:
    config = read_config(db, environment_id)
    if config is None:
        raise NotFoundError("Operations integration configuration does not exist")
    return config


@router.get("")
def list_configs(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, object]:
    require_permission(db, user, "config.read")
    settings = get_settings()
    values = list(
        db.scalars(
            select(OperationsIntegrationConfig).order_by(OperationsIntegrationConfig.created_at)
        )
    )
    return response(request, [serialize_config(db, item, settings) for item in values])


@router.post("", status_code=201)
def create_config(
    body: IntegrationConfigInput,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, object]:
    require_permission(db, user, "config.write")
    if db.scalar(select(Environment.id).where(Environment.code == body.environment.code)):
        raise AppError(409, "ENVIRONMENT_EXISTS", "Environment code already exists")
    environment = Environment(
        name=body.environment.name,
        code=body.environment.code,
        environment_level=body.environment.level,
        enabled=True,
    )
    try:
        db.add(environment)
        db.flush()
        config = save_config(db, environment, body)
    except (IntegrityError, ValueError) as exc:
        db.rollback()
        raise AppError(422, "CONFIG_REJECTED", str(exc)) from exc
    write_audit(
        db,
        "INTEGRATION_CONFIG_SAVED",
        user.username,
        "Operations integration environment created and saved as DRAFT",
        details={
            "configuration_id": config.id,
            "environment_id": environment.id,
            "status": IntegrationConfigStatus.DRAFT.value,
            "host_count": len(body.hosts),
            "service_count": len(body.services),
            "actions": body.allowlist.actions,
        },
    )
    db.commit()
    return response(request, serialize_config(db, config, get_settings()))


@router.get("/credentials")
def credentials(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, object]:
    require_permission(db, user, "config.read")
    return response(request, list_credentials(get_settings()))


@router.post("/credentials", status_code=201)
def create_credential(
    body: CredentialCreate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, object]:
    require_permission(db, user, "config.write")
    try:
        metadata = store_credential(get_settings(), body.name, body.private_key)
    except (FileExistsError, OSError, ValueError) as exc:
        raise AppError(422, "CREDENTIAL_REJECTED", str(exc)) from exc
    write_audit(
        db,
        "CREDENTIAL_CREATED",
        user.username,
        "SSH credential reference created",
        details={"credential_reference": body.name, "configured": True},
    )
    db.commit()
    return response(request, metadata)


@router.get("/{environment_id}")
def get_config(
    environment_id: str,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, object]:
    require_permission(db, user, "config.read")
    return response(
        request, serialize_config(db, _config_or_404(db, environment_id), get_settings())
    )


@router.put("/{environment_id}")
def put_config(
    environment_id: str,
    body: IntegrationConfigInput,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, object]:
    require_permission(db, user, "config.write")
    environment = db.get(Environment, environment_id)
    if environment is None:
        raise NotFoundError("Environment does not exist")
    try:
        config = save_config(db, environment, body)
    except (IntegrityError, ValueError) as exc:
        db.rollback()
        raise AppError(422, "CONFIG_REJECTED", str(exc)) from exc
    write_audit(
        db,
        "INTEGRATION_CONFIG_SAVED",
        user.username,
        "Operations integration configuration saved as DRAFT",
        details={
            "configuration_id": config.id,
            "environment_id": environment.id,
            "status": IntegrationConfigStatus.DRAFT.value,
            "host_count": len(body.hosts),
            "service_count": len(body.services),
            "actions": body.allowlist.actions,
        },
    )
    db.commit()
    return response(request, serialize_config(db, config, get_settings()))


@router.post("/{environment_id}/validate")
def validate(
    environment_id: str,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, object]:
    require_permission(db, user, "config.write")
    config = _config_or_404(db, environment_id)
    errors = validate_config(db, config, get_settings())
    write_audit(
        db,
        "INTEGRATION_CONFIG_VALIDATED",
        user.username,
        "Operations integration configuration validation completed",
        details={
            "configuration_id": config.id,
            "success": not errors,
            "error_count": len(errors),
        },
    )
    db.commit()
    return response(request, serialize_config(db, config, get_settings()))


@router.post("/{environment_id}/test-ssh/{host_id}")
def ssh_test(
    environment_id: str,
    host_id: str,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, object]:
    require_permission(db, user, "config.test")
    config = _config_or_404(db, environment_id)
    if config.enabled or config.status not in {
        IntegrationConfigStatus.VALIDATED,
        IntegrationConfigStatus.READY,
    }:
        raise AppError(
            409,
            "CONFIG_NOT_VALIDATED",
            "Configuration must be VALIDATED before SSH test",
        )
    host = db.get(Host, host_id)
    if (
        host is None
        or host.environment_id != environment_id
        or host.name not in config.allowlist.get("hosts", [])
    ):
        raise NotFoundError("Host does not exist in this configuration")
    details = test_ssh(config, host, get_settings())
    previous = config.last_test_details if isinstance(config.last_test_details, dict) else {}
    ssh_results = dict(previous.get("ssh", {})) if isinstance(previous.get("ssh"), dict) else {}
    status_results = (
        dict(previous.get("status", {})) if isinstance(previous.get("status"), dict) else {}
    )
    ssh_results[host.id] = {**details, "host_id": host.id}
    if not details["success"]:
        status_results = {
            key: value for key, value in status_results.items() if not key.startswith(f"{host.id}:")
        }
    config.last_test_details = {"ssh": ssh_results, "status": status_results}
    config.last_ssh_test_ok, config.last_status_test_ok = all_configured_tests_passed(db, config)
    config.status = IntegrationConfigStatus.VALIDATED
    write_audit(
        db,
        "INTEGRATION_SSH_TESTED",
        user.username,
        "Read-only SSH connection test completed",
        details={
            "configuration_id": config.id,
            "host_id": host.id,
            "success": details["success"],
            "latency_ms": details["latency_ms"],
            "exit_code": details["exit_code"],
        },
    )
    db.commit()
    return response(request, details)


@router.post("/{environment_id}/test-status/{host_id}/{service_id}")
def status_test(
    environment_id: str,
    host_id: str,
    service_id: str,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, object]:
    require_permission(db, user, "config.test")
    config = _config_or_404(db, environment_id)
    if config.enabled or config.status not in {
        IntegrationConfigStatus.VALIDATED,
        IntegrationConfigStatus.READY,
    }:
        raise AppError(
            409,
            "SSH_TEST_REQUIRED",
            "A successful SSH test is required before Status test",
        )
    ssh_details = config.last_test_details.get("ssh", {})
    host_ssh_details = ssh_details.get(host_id, {}) if isinstance(ssh_details, dict) else {}
    if not isinstance(host_ssh_details, dict) or host_ssh_details.get("success") is not True:
        raise AppError(
            409,
            "SSH_TEST_HOST_MISMATCH",
            "Status test must use the host that passed the SSH test",
        )
    host = db.get(Host, host_id)
    service = db.get(Service, service_id)
    deployment = db.scalar(
        select(ServiceDeployment).where(
            ServiceDeployment.host_id == host_id,
            ServiceDeployment.service_id == service_id,
            ServiceDeployment.enabled.is_(True),
        )
    )
    if (
        host is None
        or service is None
        or host.environment_id != environment_id
        or service.environment_id != environment_id
        or host.name not in config.allowlist.get("hosts", [])
        or service.name not in config.allowlist.get("services", [])
        or deployment is None
    ):
        raise NotFoundError("Enabled service/host association does not exist")
    details, result = test_status(config, config.environment, host, service, get_settings())
    status_results = config.last_test_details.get("status", {})
    status_results = dict(status_results) if isinstance(status_results, dict) else {}
    status_results[f"{host_id}:{service_id}"] = {
        **details,
        "host_id": host_id,
        "service_id": service_id,
    }
    config.last_test_details = {**config.last_test_details, "status": status_results}
    config.last_ssh_test_ok, config.last_status_test_ok = all_configured_tests_passed(db, config)
    config.status = (
        IntegrationConfigStatus.READY
        if config.last_ssh_test_ok and config.last_status_test_ok
        else IntegrationConfigStatus.VALIDATED
    )
    config.enabled = False
    write_audit(
        db,
        "INTEGRATION_STATUS_TESTED",
        user.username,
        "Read-only status execution chain test completed",
        details={
            "configuration_id": config.id,
            "host_id": host.id,
            "service_id": service.id,
            "success": result.success,
            "exit_code": result.exit_code,
            "parsed_state": result.service_state,
        },
    )
    db.commit()
    return response(request, details)


@router.post("/{environment_id}/enable")
def enable(
    environment_id: str,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, object]:
    require_permission(db, user, "config.write")
    config = _config_or_404(db, environment_id)
    errors = validate_config(db, config, get_settings())
    config.last_ssh_test_ok, config.last_status_test_ok = all_configured_tests_passed(db, config)
    if errors or not config.last_ssh_test_ok or not config.last_status_test_ok:
        raise AppError(
            409,
            "CONFIG_NOT_READY",
            "Only a successfully tested READY configuration can be enabled",
        )
    config.status = IntegrationConfigStatus.READY
    config.enabled = True
    write_audit(
        db,
        "INTEGRATION_CONFIG_ENABLED",
        user.username,
        "Operations integration configuration enabled",
        details={"configuration_id": config.id, "environment_id": environment_id},
    )
    db.commit()
    return response(request, serialize_config(db, config, get_settings()))


@router.post("/{environment_id}/disable")
def disable(
    environment_id: str,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, object]:
    require_permission(db, user, "config.write")
    config = _config_or_404(db, environment_id)
    config.enabled = False
    config.status = IntegrationConfigStatus.DISABLED
    write_audit(
        db,
        "INTEGRATION_CONFIG_DISABLED",
        user.username,
        "Operations integration configuration disabled",
        details={"configuration_id": config.id, "environment_id": environment_id},
    )
    db.commit()
    return response(request, serialize_config(db, config, get_settings()))
