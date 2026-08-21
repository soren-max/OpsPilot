import asyncio
from dataclasses import dataclass
from urllib.parse import urlsplit

from mcp import Client
from pydantic import ValidationError

from app.adapters.mcp.contracts import MCP_PROTOCOL_VERSION, McpServerTrust, McpTrustLevel
from app.adapters.mcp.errors import (
    McpMalformedResult,
    McpProtocolError,
    McpTimeout,
    McpUnavailable,
)
from app.capabilities.health import HealthObservation, HealthQuery
from app.capabilities.metrics import MetricObservation, MetricQuery


@dataclass(frozen=True)
class McpRemoteConfig:
    server_url: str
    server_name: str
    metrics_tool: str = "get_metrics"
    health_tool: str = "get_health"
    timeout_seconds: float = 5.0

    def __post_init__(self) -> None:
        parsed = urlsplit(self.server_url)
        allowed_transport = parsed.scheme == "https" or (
            parsed.scheme == "http" and parsed.hostname in {"127.0.0.1", "localhost", "::1"}
        )
        if (
            not allowed_transport
            or not parsed.hostname
            or parsed.username
            or parsed.password
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError("Remote MCP URL must use HTTPS unless it is loopback")
        allowed = {"get_metrics", "get_service_metrics", "get_health", "get_service_health"}
        if self.metrics_tool not in allowed or self.health_tool not in allowed:
            raise ValueError("Remote MCP tool mapping is outside the fixed allowlist")


class McpCapabilityClientAdapter:
    """Controlled MCP consumer: no tools/list, dynamic server selection, or model-selected names."""

    def __init__(self, config: McpRemoteConfig, trust: McpServerTrust) -> None:
        if trust.server_name != config.server_name:
            raise ValueError("MCP trust declaration must match configured server")
        self.config = config
        self.trust = trust

    async def query(self, query: MetricQuery) -> MetricObservation:
        data = await self._call(self.config.metrics_tool, query.model_dump(mode="json"))
        result = self._validate(MetricObservation, data)
        assert isinstance(result, MetricObservation)
        return result.model_copy(
            update={"source_reference": self._provenance(result.source_reference)}
        )

    async def get_service_health(self, query: HealthQuery) -> HealthObservation:
        data = await self._call(self.config.health_tool, query.model_dump(mode="json"))
        result = self._validate(HealthObservation, data)
        assert isinstance(result, HealthObservation)
        return result.model_copy(
            update={"source_reference": self._provenance(result.source_reference)}
        )

    async def _call(self, tool: str, request: dict[str, object]) -> object:
        try:
            async with asyncio.timeout(self.config.timeout_seconds):
                async with Client(self.config.server_url, mode=MCP_PROTOCOL_VERSION) as client:
                    result = await client.call_tool(tool, {"request": request})
        except TimeoutError as exc:
            raise McpTimeout("Remote MCP capability timed out") from exc
        except OSError as exc:
            raise McpUnavailable("Remote MCP capability is unavailable") from exc
        except Exception as exc:
            raise McpProtocolError("Remote MCP protocol request failed") from exc
        content = result.structured_content
        if not isinstance(content, dict):
            raise McpMalformedResult("Remote MCP result has no structured content")
        data = content.get("data", content)
        # External output remains untrusted regardless of annotations or descriptions.
        if self.trust.level is McpTrustLevel.EXTERNAL_UNTRUSTED and isinstance(data, dict):
            data = dict(data)
        return data

    def _provenance(self, remote_reference: str) -> str:
        return f"mcp:{self.config.server_name}:{remote_reference}"[:1000]

    @staticmethod
    def _validate(model: type[MetricObservation] | type[HealthObservation], data: object):
        try:
            return model.model_validate(data)
        except ValidationError as exc:
            raise McpMalformedResult("Remote MCP result violated the capability contract") from exc
