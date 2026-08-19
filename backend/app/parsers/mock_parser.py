from app.core.enums import TargetStatus
from app.executors.base import ExecutionRequest, ExecutionResult
from app.executors.transports import TransportResult
from app.parsers.json_parser import StructuredJsonParser
from app.parsers.legacy_services_parser import LegacyServicesOutputParser


class MockOutputParser:
    """Route only known fixture formats to deterministic parser strategies."""

    def __init__(self) -> None:
        self.structured = StructuredJsonParser()
        self.legacy = LegacyServicesOutputParser()

    def parse(self, request: ExecutionRequest, response: TransportResult) -> ExecutionResult:
        if response.fixture_name == "redacted-timeout":
            return ExecutionResult(
                status=TargetStatus.TIMED_OUT,
                output=None,
                error_message=response.stderr,
                duration_ms=response.duration_ms,
                exit_code=response.exit_code,
                error_code="EXECUTION_TIMEOUT",
                timed_out=True,
                retryable=True,
            )
        if response.stdout.lstrip().startswith("{"):
            return self.structured.parse(request, response)
        return self.legacy.parse(request, response)
