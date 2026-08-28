from app.domain.actions.models import (
    ActionPreview,
    ActionRequest,
    ActionResult,
    ActionStatus,
    ActionType,
    ServiceActionParams,
    VerificationResult,
)


class MockActionExecutor:
    """Deterministic, in-memory adapter that never starts a process or network call."""

    executor_name = "mock"

    def __init__(self, service_states: dict[tuple[str, str], bool] | None = None) -> None:
        self._service_states = dict(service_states or {})

    async def preview(self, action: ActionRequest) -> ActionPreview:
        return ActionPreview(
            action_type=action.action_type,
            target=action.target,
            executor=self.executor_name,
            operation=action.action_type.value,
            changes_state=action.action_type
            in {ActionType.START_SERVICE, ActionType.STOP_SERVICE, ActionType.RESTART_SERVICE},
        )

    async def execute(self, action: ActionRequest) -> ActionResult:
        if action.action_type in {
            ActionType.START_SERVICE,
            ActionType.STOP_SERVICE,
            ActionType.RESTART_SERVICE,
        }:
            if not isinstance(action.parameters, ServiceActionParams):
                raise TypeError("Service control action requires service parameters")
            service = action.parameters.service
            self._service_states[(action.target, service)] = (
                action.action_type is not ActionType.STOP_SERVICE
            )
        return ActionResult(
            action_type=action.action_type,
            target=action.target,
            status=ActionStatus.SUCCEEDED,
            summary=f"Mock action {action.action_type.value} completed.",
            executor=self.executor_name,
        )

    async def verify(self, action: ActionRequest) -> VerificationResult:
        verified = True
        if action.action_type in {
            ActionType.GET_SERVICE_STATUS,
            ActionType.START_SERVICE,
            ActionType.STOP_SERVICE,
            ActionType.RESTART_SERVICE,
        }:
            if not isinstance(action.parameters, ServiceActionParams):
                raise TypeError("Service action requires service parameters")
            service = action.parameters.service
            running = self._service_states.get((action.target, service), True)
            verified = not running if action.action_type is ActionType.STOP_SERVICE else running
        return VerificationResult(
            action_type=action.action_type,
            target=action.target,
            status=ActionStatus.SUCCEEDED if verified else ActionStatus.FAILED,
            verified=verified,
            summary="Mock verification passed." if verified else "Mock verification failed.",
        )
