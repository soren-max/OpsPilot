from app.executors.base import BaseExecutor, ExecutionRequest, ExecutionResult
from app.executors.mock import MockExecutor


class DryRunExecutor(BaseExecutor):
    """Explicit safe executor that labels all fixture outcomes as dry-run."""

    executor_type = "dry_run"

    def __init__(self, delegate: MockExecutor | None = None) -> None:
        self.delegate = delegate or MockExecutor()

    def _execute(self, request: ExecutionRequest) -> ExecutionResult:
        return self.delegate.execute(request)
