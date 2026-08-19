from app.core.enums import OperationAction, TargetStatus
from app.executors.base import BaseExecutor, ExecutionRequest, ExecutionResult
from app.executors.transports import FakeTransport
from app.parsers import MockOutputParser, OutputParser


class MockExecutor(BaseExecutor):
    """Deterministic executor. It performs no network or subprocess operations."""

    executor_type = "mock"
    supported_actions = frozenset(
        {OperationAction.STATUS, OperationAction.START, OperationAction.STOP}
    )

    def __init__(
        self,
        transport: FakeTransport | None = None,
        parser: OutputParser | None = None,
    ) -> None:
        self.transport = transport or FakeTransport()
        self.parser = parser or MockOutputParser()

    def _execute(self, request: ExecutionRequest) -> ExecutionResult:
        if request.action not in {
            OperationAction.STATUS,
            OperationAction.START,
            OperationAction.STOP,
        }:
            return ExecutionResult(
                status=TargetStatus.FAILED,
                output=None,
                error_message="Mock executor permits only simulated status/start/stop",
                duration_ms=1,
            )
        return self.parser.parse(request, self.transport.run(request))
