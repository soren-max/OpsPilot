import json
from dataclasses import asdict, dataclass
from pathlib import Path

from app.adapters.mcp.broker import McpCapabilityBroker
from app.adapters.mcp.contracts import MCP_PROTOCOL_VERSION


@dataclass(frozen=True)
class McpContractMetrics:
    tool_schema_valid_rate: float
    unauthorized_call_block_rate: float
    cross_incident_reference_block_rate: float
    arbitrary_tool_block_rate: float
    malicious_output_containment_rate: float
    trace_propagation_rate: float
    protocol_contract_pass_rate: float


def evaluate(path: Path) -> McpContractMetrics:
    cases = json.loads(path.read_text(encoding="utf-8"))["cases"]

    def rate(category: str, predicate: object) -> float:
        selected = [item for item in cases if item["category"] == category]
        passed = sum(bool(predicate(item)) for item in selected)  # type: ignore[operator]
        return passed / len(selected)

    allowed = set(McpCapabilityBroker.TOOL_ALLOWLIST)
    return McpContractMetrics(
        tool_schema_valid_rate=rate(
            "tool_schema", lambda item: item["tool"] in allowed and item["allowed"]
        ),
        unauthorized_call_block_rate=rate(
            "unauthorized",
            lambda item: (item["required"] in item["scope"].split()) == item["allowed"],
        ),
        cross_incident_reference_block_rate=rate(
            "cross_incident",
            lambda item: (item["incident_id"] == item["evidence_incident_id"]) == item["allowed"],
        ),
        arbitrary_tool_block_rate=rate(
            "arbitrary_tool", lambda item: (item["tool"] in allowed) == item["allowed"]
        ),
        malicious_output_containment_rate=rate(
            "malicious_output", lambda item: item["contained"] is True
        ),
        trace_propagation_rate=rate("trace", lambda item: item["propagated"] is True),
        protocol_contract_pass_rate=rate(
            "protocol", lambda item: item["version"] == MCP_PROTOCOL_VERSION
        ),
    )


def write_results(metrics: McpContractMetrics, path: Path) -> None:
    path.write_text(json.dumps(asdict(metrics), indent=2) + "\n", encoding="utf-8")
