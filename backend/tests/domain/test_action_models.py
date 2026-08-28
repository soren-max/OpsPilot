import pytest
from pydantic import ValidationError

from app.domain.actions.models import (
    ActionRequest,
    ActionType,
    HealthCheckParams,
    ServiceActionParams,
    TargetEnvironment,
)


def service_request(action_type: ActionType = ActionType.GET_SERVICE_STATUS) -> ActionRequest:
    return ActionRequest(
        action_type=action_type,
        target="web-01",
        environment=TargetEnvironment.TEST,
        parameters=ServiceActionParams(service="nginx"),
        reason="Investigate the unavailable web service.",
    )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("target", "web-01; shutdown"),
        ("target", ""),
        ("reason", "no"),
        ("environment", "unknown"),
    ],
)
def test_malformed_action_request_is_rejected(field: str, value: str) -> None:
    payload = service_request().model_dump()
    payload[field] = value
    with pytest.raises(ValidationError):
        ActionRequest.model_validate(payload)


def test_unknown_action_and_extra_parameters_are_rejected() -> None:
    payload = service_request().model_dump()
    payload["action_type"] = "run_shell"
    with pytest.raises(ValidationError):
        ActionRequest.model_validate(payload)

    with pytest.raises(ValidationError):
        ServiceActionParams.model_validate({"service": "nginx", "command": "id"})


def test_parameter_schema_must_match_action() -> None:
    request = ActionRequest(
        action_type=ActionType.HEALTH_CHECK,
        target="web-01",
        environment=TargetEnvironment.TEST,
        parameters=HealthCheckParams(service="nginx"),
        reason="Check health endpoint.",
    )
    assert request.parameters.service == "nginx"

    with pytest.raises(ValidationError):
        ActionRequest.model_validate(
            {
                **request.model_dump(),
                "parameters": {
                    "service": "nginx",
                    "path": "/caller-selected",
                    "expected_status": 204,
                },
            }
        )


def test_agent_safety_case_cannot_become_arbitrary_process_kill() -> None:
    payload = {
        "action_type": "kill_processes",
        "target": "web-01",
        "environment": "test",
        "parameters": {"command": "kill -9 all"},
        "reason": "The user asked to kill the highest CPU processes.",
    }
    with pytest.raises(ValidationError):
        ActionRequest.model_validate(payload)
