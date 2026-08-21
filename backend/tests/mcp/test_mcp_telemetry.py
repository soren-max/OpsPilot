import asyncio

from mcp import Client
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from app.adapters.mcp.contracts import MCP_PROTOCOL_VERSION
from app.adapters.mcp.server import build_mcp_server
from tests.mcp.test_mcp_server import broker


def test_mcp_tool_and_capability_share_trace_without_sensitive_attributes() -> None:
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    trace.set_tracer_provider(provider)

    async def run() -> None:
        capability_broker, _ = broker()
        async with Client(build_mcp_server(capability_broker), mode=MCP_PROTOCOL_VERSION) as client:
            await client.call_tool(
                "get_service_health",
                {"request": {"service": "web", "environment": "test"}},
            )

    asyncio.run(run())
    spans = exporter.get_finished_spans()
    tool = next(span for span in spans if span.name == "mcp.tools.call")
    capability = next(span for span in spans if span.name == "opspilot.capability.invoke")
    assert tool.context is not None and capability.context is not None
    assert tool.context.trace_id == capability.context.trace_id
    attributes = {key for span in spans for key in (span.attributes or {})}
    assert "authorization" not in attributes
    assert "raw_logs" not in attributes
    assert "prompt" not in attributes
