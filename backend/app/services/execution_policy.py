import re
from dataclasses import dataclass

from app.core.config import Settings
from app.core.enums import EnvironmentLevel, OperationAction

SAFE_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:@-]{0,127}$")
WRITE_ACTIONS = {
    OperationAction.START,
    OperationAction.STOP,
    OperationAction.RESTART,
    OperationAction.DEPLOY,
}


@dataclass(frozen=True)
class PolicyRejection(Exception):
    code: str
    message: str
    field: str | None = None


def validate_execution_target(
    settings: Settings,
    *,
    action: OperationAction,
    environment: str,
    host: str,
    service: str,
    environment_level: EnvironmentLevel,
    approval_granted: bool = False,
    allowed_environments: frozenset[str] | None = None,
    allowed_hosts: frozenset[str] | None = None,
    allowed_services: frozenset[str] | None = None,
    allowed_actions: frozenset[str] | None = None,
    require_execution_acknowledgement: bool = False,
) -> None:
    """Fail closed before executor construction or subprocess creation."""
    for field, value, allowlist in (
        ("environment", environment, allowed_environments or settings.allowed_environment_set),
        ("host", host, allowed_hosts or settings.allowed_host_set),
        ("service", service, allowed_services or settings.allowed_service_set),
    ):
        if not allowlist or value not in allowlist:
            raise PolicyRejection(
                f"{field.upper()}_NOT_ALLOWED",
                f"{field.capitalize()} is outside the configured allowlist",
                field,
            )
    for field, value in (
        ("environment", environment),
        ("host", host),
        ("service", service),
    ):
        if not SAFE_IDENTIFIER.fullmatch(value):
            raise PolicyRejection(
                "UNSAFE_TARGET_IDENTIFIER",
                f"{field.capitalize()} contains unsupported characters",
                field,
            )
    # Check the write switch before the action allowlist so a globally closed
    # deployment returns a stable, operator-friendly rejection.
    if action in WRITE_ACTIONS and not settings.write_operations_enabled:
        raise PolicyRejection(
            "WRITE_OPERATION_DISABLED",
            "当前阶段仅允许 status 查询",
            "action",
        )
    if (
        action in WRITE_ACTIONS
        and require_execution_acknowledgement
        and not settings.execution_is_acknowledged
    ):
        raise PolicyRejection(
            "EXECUTION_NOT_ACKNOWLEDGED",
            "Write execution has not been explicitly acknowledged",
            "action",
        )
    effective_actions = allowed_actions or settings.allowed_action_set
    if not effective_actions or action.value not in effective_actions:
        raise PolicyRejection(
            "ACTION_NOT_ALLOWED",
            "Action is outside the configured allowlist",
            "action",
        )
    if (
        action in WRITE_ACTIONS
        and environment_level is EnvironmentLevel.PRODUCTION
        and not settings.production_operations_enabled
    ):
        raise PolicyRejection(
            "PRODUCTION_OPERATION_DISABLED",
            "Production start/stop operations are disabled by platform policy",
            "environment",
        )
    if action in WRITE_ACTIONS and settings.approval_required_for_write and not approval_granted:
        raise PolicyRejection(
            "APPROVAL_REQUIRED",
            "Write operation requires approval, but no approved request was supplied",
            "action",
        )
