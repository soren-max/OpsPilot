import re
from dataclasses import dataclass
from typing import ClassVar

from app.core.enums import OperationAction
from app.executors.base import ExecutionRequest, ExecutionResult
from app.executors.transports import TransportResult
from app.parsers import LegacyServicesOutputParser, OutputParser

SAFE_ARGUMENT = re.compile(r"^[A-Za-z0-9_.-]+$")


@dataclass(frozen=True)
class ServicesAdapterConfig:
    script_path: str


class ServicesAdapter:
    """Protocol-only adapter for a future approved services.sh implementation."""

    ALLOWED_ACTIONS: ClassVar[set[OperationAction]] = {
        OperationAction.STATUS,
        OperationAction.START,
        OperationAction.STOP,
    }

    def __init__(
        self,
        config: ServicesAdapterConfig,
        parser: OutputParser | None = None,
    ) -> None:
        self.config = config
        self.parser = parser or LegacyServicesOutputParser()

    def build_command(self, request: ExecutionRequest) -> list[str]:
        if request.action not in self.ALLOWED_ACTIONS:
            raise ValueError("services.sh adapter permits only status, start, and stop")
        if not SAFE_ARGUMENT.fullmatch(request.service_name):
            raise ValueError("Service name contains unsupported characters")
        return [
            self.config.script_path,
            request.action.value,
            request.service_name,
        ]

    def parse_result(
        self,
        request: ExecutionRequest,
        response: TransportResult,
    ) -> ExecutionResult:
        return self.parser.parse(request, response)
