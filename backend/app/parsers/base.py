from typing import Protocol

from app.executors.base import ExecutionRequest, ExecutionResult
from app.executors.transports import TransportResult
from app.parsers.status_result import ParsedOutput


class OutputParser(Protocol):
    def parse(self, request: ExecutionRequest, response: TransportResult) -> ExecutionResult: ...


class StatusOutputParser(Protocol):
    """Parser contract for untrusted services.sh status process output."""

    def parse(self, stdout: str, stderr: str, exit_code: int) -> ParsedOutput: ...
