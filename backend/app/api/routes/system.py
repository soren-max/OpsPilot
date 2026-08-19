from fastapi import APIRouter, Depends, Request
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.api.deps import response
from app.core.config import get_settings
from app.core.enums import IntegrationConfigStatus
from app.db.session import get_db
from app.models import OperationsIntegrationConfig
from app.services.readiness import (
    dynamic_configuration_readiness,
    local_services_bootstrap_readiness,
    local_services_readiness,
)

router = APIRouter(tags=["system"])


@router.get("/health")
def health(request: Request) -> dict[str, object]:
    return response(
        request,
        {
            "status": "ok",
            "application": "responsive",
        },
    )


@router.get("/ready")
def ready(request: Request, db: Session = Depends(get_db)) -> dict[str, object]:
    settings = get_settings()
    db.execute(text("SELECT 1"))
    valid_executors = {
        "mock",
        "dry_run",
        "local_services",
        "ansible_playbook",
        "ansible",
    }
    executor_status = (
        "configured" if settings.selected_executor in valid_executors else "not_configured"
    )
    local_services = settings.selected_executor == "local_services"
    dynamic_preflight = dynamic_configuration_readiness(db, settings)
    preflight = (
        local_services_bootstrap_readiness(db, settings)
        if local_services and dynamic_preflight is not None
        else local_services_readiness(db, settings)
        if local_services
        else None
    )
    profile = settings.command_profiles.get(settings.services_command_profile)
    profile_check = (
        preflight["checks"].get("command_profile") if preflight is not None else None
    )
    dynamic_actions = sorted(
        {
            action
            for config in db.scalars(
                select(OperationsIntegrationConfig).where(
                    OperationsIntegrationConfig.status == IntegrationConfigStatus.READY,
                    OperationsIntegrationConfig.enabled.is_(True),
                )
            )
            for action in config.allowlist.get("actions", [])
        }
    )
    capabilities = (
        dynamic_actions
        if dynamic_preflight is not None
        else sorted(action for action in profile.capabilities if action in profile.actions)
        if profile is not None
        else []
    )
    checks_ok = (
        executor_status == "configured"
        and (preflight is None or preflight["status"] == "ready")
        and (dynamic_preflight is None or dynamic_preflight["status"] == "ready")
    )
    return response(
        request,
        {
            "status": "ready" if checks_ok else "not_ready",
            "configuration": "configured",
            "database": "available",
            "worker": {
                "status": "configured",
                "poll_seconds": settings.worker_poll_seconds,
            },
            "executor": {
                "type": settings.selected_executor,
                "status": executor_status,
            },
            "services": {
                "required": local_services,
                "command_profile": (
                    "configured"
                    if dynamic_preflight is not None
                    or (profile_check and profile_check["status"] == "ok")
                    else "not_configured"
                ),
                "profile_name": (
                    "dynamic-operations"
                    if dynamic_preflight is not None
                    else settings.services_command_profile
                ),
                "profile_error": (
                    profile_check["reason"]
                    if profile_check and profile_check["status"] != "ok"
                    else None
                ),
                "capabilities": capabilities,
                "preflight": preflight,
            },
            "operations_integration": {
                "required": dynamic_preflight is not None,
                "preflight": dynamic_preflight,
            },
        },
    )
