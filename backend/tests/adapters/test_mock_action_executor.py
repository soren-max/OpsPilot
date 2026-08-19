import asyncio

from app.adapters.mock import MockActionExecutor
from app.application import ActionService
from app.domain.actions.models import (
    ActionRequest,
    ActionType,
    ServiceActionParams,
    TargetEnvironment,
)
from app.domain.actions.policy import ActionPolicyEngine


def restart_request() -> ActionRequest:
    return ActionRequest(
        action_type=ActionType.RESTART_SERVICE,
        target="web-01",
        environment=TargetEnvironment.TEST,
        parameters=ServiceActionParams(service="nginx"),
        reason="Service status evidence shows nginx is unavailable.",
    )


def test_application_service_never_executes_medium_action_without_approval() -> None:
    executor = MockActionExecutor({("web-01", "nginx"): False})
    service = ActionService(ActionPolicyEngine(frozenset({"web-01"})), executor)

    blocked = asyncio.run(service.execute(restart_request()))
    assert blocked.assessment.allowed is False
    assert blocked.result is None

    executed = asyncio.run(service.execute(restart_request(), approval_granted=True))
    assert executed.result is not None
    assert executed.verification is not None
    assert executed.verification.verified is True
