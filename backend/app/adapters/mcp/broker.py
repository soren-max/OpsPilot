import asyncio
from collections.abc import Awaitable, Coroutine
from typing import Protocol, TypeVar

from opentelemetry import trace

from app.adapters.mcp.contracts import (
    HealthToolInput,
    KnowledgeToolInput,
    LogsToolInput,
    MetricsToolInput,
    RemediationProposalResult,
    RemediationToolInput,
    TicketsToolInput,
    ToolEnvelope,
)
from app.capabilities.health import HealthCapability, HealthQuery
from app.capabilities.logs import LogQuery, LogsCapability, LogSeverity
from app.capabilities.metrics import MetricAggregation, MetricKind, MetricQuery, MetricsCapability
from app.capabilities.policy import CapabilityQueryPolicy
from app.capabilities.tickets import TicketQuery, TicketsCapability
from app.domain.incidents.memory import KnowledgeQuery, KnowledgeRetriever

tracer = trace.get_tracer("opspilot.mcp")
InvokeResult = TypeVar("InvokeResult")


class GovernedActionProposer(Protocol):
    async def propose(
        self, request: RemediationToolInput, actor: str
    ) -> RemediationProposalResult: ...


class McpCapabilityBroker:
    """Fixed MCP-to-port mapping. It never performs dynamic Python dispatch or authorization."""

    TOOL_ALLOWLIST = (
        "get_service_metrics",
        "search_service_logs",
        "search_incident_tickets",
        "get_service_health",
        "retrieve_historical_incidents",
        "request_remediation",
    )

    def __init__(
        self,
        policy: CapabilityQueryPolicy,
        *,
        metrics: MetricsCapability | None = None,
        logs: LogsCapability | None = None,
        tickets: TicketsCapability | None = None,
        health: HealthCapability | None = None,
        knowledge: KnowledgeRetriever | None = None,
        action_proposer: GovernedActionProposer | None = None,
        timeout_seconds: float = 5.0,
        max_concurrency: int = 8,
        provenance: str = "native",
    ) -> None:
        self.policy = policy
        self.metrics = metrics
        self.logs = logs
        self.tickets = tickets
        self.health = health
        self.knowledge = knowledge
        self.action_proposer = action_proposer
        self.timeout_seconds = timeout_seconds
        self.provenance = provenance
        self._semaphore = asyncio.Semaphore(max_concurrency)
        self._failures: dict[str, int] = {}

    async def get_service_metrics(self, request: MetricsToolInput) -> ToolEnvelope:
        if self.metrics is None:
            raise RuntimeError("Metrics capability is unavailable")
        query = MetricQuery(
            metric_kind=MetricKind(request.metric_kind),
            service=request.service,
            environment=request.environment,
            start=request.start,
            end=request.end,
            step_seconds=request.step_seconds,
            aggregation=MetricAggregation.AVG,
        )
        self.policy.validate_metric(query)
        result = await self._invoke("metrics", self.metrics.query(query))
        self.policy.validate_series_count(len(result.series))
        return self._envelope("metrics", result.model_dump(mode="json"))

    async def search_service_logs(self, request: LogsToolInput) -> ToolEnvelope:
        if self.logs is None:
            raise RuntimeError("Logs capability is unavailable")
        query = LogQuery(
            service=request.service,
            environment=request.environment,
            start=request.start,
            end=request.end,
            severity=LogSeverity(request.severity) if request.severity else None,
            keywords=request.keywords,
            limit=request.limit,
        )
        self.policy.validate_log(query)
        result = await self._invoke("logs", self.logs.query(query))
        return self._envelope("logs", result.model_dump(mode="json"))

    async def search_incident_tickets(self, request: TicketsToolInput) -> ToolEnvelope:
        if self.tickets is None:
            raise RuntimeError("Tickets capability is unavailable")
        query = TicketQuery(
            service=request.service,
            environment=request.environment,
            start=request.start,
            end=request.end,
            status=request.status,
            keywords=request.keywords,
            limit=request.limit,
        )
        self.policy.validate_ticket(query)
        result = await self._invoke("tickets", self.tickets.search(query))
        return self._envelope("tickets", [item.model_dump(mode="json") for item in result])

    async def get_service_health(self, request: HealthToolInput) -> ToolEnvelope:
        if self.health is None:
            raise RuntimeError("Health capability is unavailable")
        self.policy.validate_service(request.service)
        result = await self._invoke(
            "health",
            self.health.get_service_health(
                HealthQuery(service=request.service, environment=request.environment)
            ),
        )
        return self._envelope("health", result.model_dump(mode="json"))

    async def retrieve_historical_incidents(self, request: KnowledgeToolInput) -> ToolEnvelope:
        if self.knowledge is None:
            raise RuntimeError("Knowledge capability is unavailable")
        self.policy.validate_service(request.service)
        query = KnowledgeQuery(
            service=request.service,
            environment=request.environment,
            symptoms=request.symptoms,
            evidence_summary=request.evidence_summary,
            limit=request.limit,
            severity=request.severity,
            tags=request.tags,
        )
        result = await self._invoke("knowledge", asyncio.to_thread(self.knowledge.retrieve, query))
        safe = [
            {
                "knowledge_id": item.knowledge_id,
                "incident_id": item.incident_id,
                "title": item.title,
                "service": item.service,
                "environment": item.environment,
                "root_cause": item.root_cause,
                "remediation": list(item.remediation),
                "verification": list(item.verification),
                "retrieval_score": item.retrieval_score,
                "source_reference": item.source_reference,
                "resolved_at": item.resolved_at.isoformat(),
            }
            for item in result
        ]
        return self._envelope("knowledge", safe)

    async def request_remediation(
        self, request: RemediationToolInput, *, actor: str
    ) -> RemediationProposalResult:
        if self.action_proposer is None:
            raise RuntimeError("Governed action proposal is unavailable")
        return await self._invoke("action.propose", self.action_proposer.propose(request, actor))

    async def _invoke(
        self, capability: str, call: Awaitable[InvokeResult]
    ) -> InvokeResult:
        if self._failures.get(capability, 0) >= 3:
            if isinstance(call, Coroutine):
                call.close()
            raise RuntimeError(f"{capability} circuit is open")
        with tracer.start_as_current_span("opspilot.capability.invoke") as span:
            span.set_attribute("capability", capability)
            try:
                async with self._semaphore:
                    result = await asyncio.wait_for(call, timeout=self.timeout_seconds)
            except Exception:
                self._failures[capability] = self._failures.get(capability, 0) + 1
                raise
            self._failures[capability] = 0
            return result

    def _envelope(self, capability: str, data: object) -> ToolEnvelope:
        return ToolEnvelope(capability=capability, provenance=self.provenance, data=data)
