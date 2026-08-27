import pytest

from app.domain.actions.models import (
    ActionRequest,
    ActionType,
    HealthCheckParams,
    RiskLevel,
    ServiceActionParams,
    TargetEnvironment,
)
from app.domain.actions.policy import ActionPolicyEngine


def request(action_type: ActionType, target: str = "web-01") -> ActionRequest:
    parameters = (
        HealthCheckParams(service="nginx")
        if action_type is ActionType.HEALTH_CHECK
        else ServiceActionParams(service="nginx")
    )
    return ActionRequest(
        action_type=action_type,
        target=target,
        environment=TargetEnvironment.TEST,
        parameters=parameters,
        reason="Collect evidence before taking action.",
    )


@pytest.mark.parametrize(
    "action_type",
    [ActionType.GET_SERVICE_STATUS, ActionType.HEALTH_CHECK],
)
def test_read_only_actions_are_automatically_allowed(action_type: ActionType) -> None:
    assessment = ActionPolicyEngine(frozenset({"web-01"})).assess(request(action_type))
    assert assessment.risk_level is RiskLevel.READ_ONLY
    assert assessment.allowed is True
    assert assessment.approval_required is False


@pytest.mark.parametrize(
    "action_type",
    [ActionType.START_SERVICE, ActionType.STOP_SERVICE, ActionType.RESTART_SERVICE],
)
@pytest.mark.parametrize("approval_granted", [False, True])
def test_medium_action_requires_approval(
    action_type: ActionType, approval_granted: bool
) -> None:
    assessment = ActionPolicyEngine(frozenset({"web-01"})).assess(
        request(action_type), approval_granted=approval_granted
    )
    assert assessment.risk_level is RiskLevel.MEDIUM
    assert assessment.approval_required is True
    assert assessment.allowed is approval_granted


def test_unknown_target_is_fail_closed() -> None:
    assessment = ActionPolicyEngine(frozenset({"web-01"})).assess(
        request(ActionType.GET_SERVICE_STATUS, target="unknown-host")
    )
    assert assessment.risk_level is RiskLevel.FORBIDDEN
    assert assessment.allowed is False
    assert assessment.policy_rule == "target.allowlist"
