import asyncio

from app.application import ActionService
from app.core.config import Settings
from app.domain.actions.models import (
    ActionPreview,
    ActionRequest,
    ActionResult,
    ActionStatus,
    ActionType,
    ServiceActionParams,
    TargetEnvironment,
    VerificationResult,
)
from app.domain.actions.policy import ActionPolicyEngine
from app.services.worker import WorkerService


def action() -> ActionRequest:
    return ActionRequest(
        action_type=ActionType.GET_SERVICE_STATUS,
        target="target-a",
        environment=TargetEnvironment.TEST,
        parameters=ServiceActionParams(service="gateway"),
        reason="Confirm the service state before remediation.",
    )


class FlakyExecutor:
    executor_name = "test"

    def __init__(self) -> None:
        self.execute_calls = 0

    async def preview(self, request: ActionRequest) -> ActionPreview:
        return ActionPreview(
            action_type=request.action_type,
            target=request.target,
            executor=self.executor_name,
            operation="status",
            changes_state=False,
        )

    async def execute(self, request: ActionRequest) -> ActionResult:
        self.execute_calls += 1
        status = ActionStatus.FAILED if self.execute_calls == 1 else ActionStatus.SUCCEEDED
        return ActionResult(
            action_type=request.action_type,
            target=request.target,
            status=status,
            summary=status.value,
            executor=self.executor_name,
        )

    async def verify(self, request: ActionRequest) -> VerificationResult:
        return VerificationResult(
            action_type=request.action_type,
            target=request.target,
            status=ActionStatus.SUCCEEDED,
            verified=True,
            summary="verified",
        )


class SlowExecutor(FlakyExecutor):
    async def execute(self, request: ActionRequest) -> ActionResult:
        await asyncio.sleep(2)
        return await super().execute(request)


def settings(*, executor_retry: int = 0, execution_timeout_seconds: int = 30) -> Settings:
    return Settings(
        secret_key="test-secret-key-with-at-least-32-characters",
        executor_retry=executor_retry,
        execution_timeout_seconds=execution_timeout_seconds,
    )


def test_worker_retries_failed_structured_action(db) -> None:
    executor = FlakyExecutor()
    service = ActionService(ActionPolicyEngine(frozenset({"target-a"})), executor)
    run = WorkerService(db, service, settings(executor_retry=1))._execute_one(
        action(), approval_granted=False
    )

    assert run.attempts == 2
    assert run.outcome.result is not None
    assert run.outcome.result.status is ActionStatus.SUCCEEDED
    assert executor.execute_calls == 2


def test_worker_times_out_structured_action(db) -> None:
    service = ActionService(ActionPolicyEngine(frozenset({"target-a"})), SlowExecutor())
    run = WorkerService(
        db, service, settings(execution_timeout_seconds=1)
    )._execute_one(action(), approval_granted=False)

    assert run.timed_out is True
    assert run.attempts == 1
    assert run.outcome.result is None
