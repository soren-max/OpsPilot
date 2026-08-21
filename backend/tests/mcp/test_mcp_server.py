import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from mcp import Client

from app.adapters.mcp.broker import McpCapabilityBroker
from app.adapters.mcp.contracts import (
    MCP_PROTOCOL_VERSION,
    RemediationProposalResult,
    RemediationToolInput,
)
from app.adapters.mcp.server import build_mcp_server
from app.capabilities.health import HealthObservation, HealthQuery, HealthStatus
from app.capabilities.policy import CapabilityQueryPolicy


class FakeHealth:
    async def get_service_health(self, query: HealthQuery) -> HealthObservation:
        now = datetime.now(UTC)
        return HealthObservation(
            service=query.service,
            environment=query.environment,
            status=HealthStatus.UNAVAILABLE,
            summary="service unavailable",
            source_reference="health://web",
            observed_at=now,
            collected_at=now,
        )


class FakeProposer:
    def __init__(self) -> None:
        self.requests: list[RemediationToolInput] = []

    async def propose(self, request: RemediationToolInput, actor: str) -> RemediationProposalResult:
        self.requests.append(request)
        return RemediationProposalResult(
            status="approval_required",
            risk_level="medium",
            approval_required=True,
            approval_id="approval-1",
            workflow_id="workflow-1",
        )


class FakeResources:
    def incident(self, incident_id: str) -> dict[str, object]:
        return {"incident_id": incident_id, "title": "Bounded incident"}

    def evidence(self, incident_id: str) -> list[dict[str, object]]:
        return [{"evidence_id": "e-1", "incident_id": incident_id}]

    def timeline(self, incident_id: str) -> list[dict[str, object]]:
        return [{"incident_id": incident_id, "event_type": "INCIDENT_CREATED"}]

    def knowledge(self, incident_id: str) -> dict[str, object]:
        return {"incident_id": incident_id, "root_cause": "process unavailable"}


def broker() -> tuple[McpCapabilityBroker, FakeProposer]:
    proposer = FakeProposer()
    return (
        McpCapabilityBroker(
            CapabilityQueryPolicy(frozenset({"web"}), max_time_range=timedelta(hours=1)),
            health=FakeHealth(),
            action_proposer=proposer,
        ),
        proposer,
    )


@pytest.mark.asyncio
async def test_official_client_discovers_typed_tools_and_reads_resource() -> None:
    capability_broker, _ = broker()
    server = build_mcp_server(capability_broker, FakeResources())
    async with Client(server, mode=MCP_PROTOCOL_VERSION) as client:
        tools = await client.list_tools()
        names = [tool.name for tool in tools.tools]
        assert names == list(McpCapabilityBroker.TOOL_ALLOWLIST)
        health = await client.call_tool(
            "get_service_health",
            {"request": {"service": "web", "environment": "production"}},
        )
        assert health.structured_content is not None
        assert health.structured_content["capability"] == "health"
        assert health.structured_content["data"]["status"] == "UNAVAILABLE"
        listed = {tool.name: tool for tool in tools.tools}
        assert listed["get_service_health"].annotations is not None
        assert listed["get_service_health"].annotations.read_only_hint is True
        templates = await client.list_resource_templates()
        assert len(templates.resource_templates) == 4
        resource = await client.read_resource("opspilot://incidents/incident-1")
        payload = json.loads(resource.contents[0].text)  # type: ignore[union-attr]
        assert payload["protocol_version"] == MCP_PROTOCOL_VERSION
        assert payload["data"]["incident_id"] == "incident-1"


@pytest.mark.asyncio
async def test_server_discover_negotiates_current_protocol_without_initialize() -> None:
    capability_broker, _ = broker()
    async with Client(build_mcp_server(capability_broker), mode="auto") as client:
        assert client.protocol_version == MCP_PROTOCOL_VERSION
        assert (await client.list_tools()).tools


@pytest.mark.asyncio
async def test_tool_contract_snapshot() -> None:
    snapshot = json.loads(
        (Path(__file__).with_name("snapshots") / "tool_contracts.json").read_text(
            encoding="utf-8"
        )
    )
    capability_broker, _ = broker()
    async with Client(build_mcp_server(capability_broker), mode=MCP_PROTOCOL_VERSION) as client:
        tools = await client.list_tools()
    assert snapshot["protocol_version"] == MCP_PROTOCOL_VERSION
    assert snapshot["tools"] == [tool.name for tool in tools.tools]
    assert all(
        any(
            definition.get("additionalProperties") is False
            for definition in tool.input_schema.get("$defs", {}).values()
        )
        for tool in tools.tools
    )
    assert all(tool.output_schema is not None for tool in tools.tools)


@pytest.mark.asyncio
async def test_mutating_tool_only_returns_durable_approval_boundary() -> None:
    capability_broker, proposer = broker()
    async with Client(build_mcp_server(capability_broker), mode=MCP_PROTOCOL_VERSION) as client:
        result = await client.call_tool(
            "request_remediation",
            {
                "request": {
                    "incident_id": "incident-1",
                    "action_type": "restart_service",
                    "target": "web",
                    "reason": "current health evidence shows unavailable",
                    "evidence_ids": ["evidence-1"],
                }
            },
        )
        assert result.structured_content == {
            "schema_version": "1",
            "status": "approval_required",
            "risk_level": "medium",
            "approval_required": True,
            "approval_id": "approval-1",
            "workflow_id": "workflow-1",
        }
        assert proposer.requests[0].evidence_ids == ("evidence-1",)


@pytest.mark.asyncio
async def test_arbitrary_tool_is_not_exposed() -> None:
    capability_broker, _ = broker()
    async with Client(build_mcp_server(capability_broker), mode=MCP_PROTOCOL_VERSION) as client:
        result = await client.call_tool("run_shell", {"command": "id"})
        assert result.is_error is True
