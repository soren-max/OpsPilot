import asyncio
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.adapters.mock import MockActionExecutor
from app.application import ActionService
from app.application.incident_service import IncidentService
from app.application.workflow_service import WorkflowService
from app.capabilities import IncidentCapabilities
from app.capabilities.errors import CapabilityUnavailable
from app.capabilities.health import HealthObservation, HealthQuery, HealthStatus
from app.capabilities.logs import LogEntry, LogObservation, LogQuery
from app.capabilities.metrics import (
    MetricObservation,
    MetricPoint,
    MetricQuery,
    MetricsCapability,
    MetricSeries,
)
from app.capabilities.policy import CapabilityQueryPolicy
from app.capabilities.tickets import TicketQuery, TicketRecord
from app.domain.actions.policy import ActionPolicyEngine
from app.domain.audit.models import AuditEventType
from app.domain.incidents.evidence import EvidenceType
from app.repositories.workflow_models import WorkflowRunStatus
from app.workflows.incident.context import IncidentWorkflowRuntime
from app.workflows.incident.investigator import DeterministicInvestigator
from tests.workflows.test_incident_workflow import create_incident

NOW = datetime(2026, 8, 20, tzinfo=UTC)


class FixtureMetrics:
    async def query(self, query: MetricQuery) -> MetricObservation:
        return MetricObservation(
            query_kind=query.metric_kind,
            service=query.service,
            environment=query.environment,
            start=query.start,
            end=query.end,
            series=(
                MetricSeries(
                    labels={"instance": "web-01"},
                    points=(MetricPoint(timestamp=query.end, value=0.0),),
                ),
            ),
            summary="SERVICE_UP is 0 for the web service.",
            source_reference="prometheus:query:fixture-service-up",
            collected_at=NOW,
        )


class FixtureLogs:
    async def query(self, query: LogQuery) -> LogObservation:
        return LogObservation(
            service=query.service,
            environment=query.environment,
            start=query.start,
            end=query.end,
            entries=(
                LogEntry(
                    timestamp=query.end,
                    level="error",
                    message_excerpt="upstream connection refused; returning 503",
                    labels={"service": query.service, "level": "error"},
                    source_reference="loki:entry:fixture-error",
                ),
            ),
            summary="Recent ERROR log entries show connection refusal.",
            source_reference="loki:query:fixture-errors",
            collected_at=NOW,
        )


class FixtureTickets:
    async def search(self, query: TicketQuery) -> tuple[TicketRecord, ...]:
        return (
            TicketRecord(
                id="INC-100",
                title="Previous web service outage",
                status="resolved",
                service=query.service,
                environment=query.environment,
                summary="Previous related 5xx incident",
                resolution="Service restart restored traffic",
                created_at=query.end,
                resolved_at=query.end,
                source_reference="ticket:INC-100",
            ),
        )


class FixtureHealth:
    async def get_service_health(self, query: HealthQuery) -> HealthObservation:
        return HealthObservation(
            service=query.service,
            environment=query.environment,
            status=HealthStatus.UNAVAILABLE,
            summary=f"Service {query.service} is unavailable.",
            source_reference="health:target:web-01",
            observed_at=NOW,
            collected_at=NOW,
        )


class FailingMetrics:
    async def query(self, query: MetricQuery) -> MetricObservation:
        del query
        raise CapabilityUnavailable("Prometheus unavailable")


def fixture_capabilities(
    *, metrics: MetricsCapability | None = None
) -> IncidentCapabilities:
    return IncidentCapabilities(
        policy=CapabilityQueryPolicy(allowed_services=frozenset({"mock-service"})),
        metrics=metrics if metrics is not None else FixtureMetrics(),
        logs=FixtureLogs(),
        tickets=FixtureTickets(),
        health=FixtureHealth(),
        timeout_seconds=0.5,
    )


def action_service() -> ActionService:
    return ActionService(
        ActionPolicyEngine(frozenset({"mock-service"})), MockActionExecutor()
    )


def test_collect_context_normalizes_and_deduplicates_evidence(db: Session) -> None:
    incident_id = create_incident(db)
    service = WorkflowService(db, capabilities=fixture_capabilities())
    workflow = service.start(incident_id, "operator", "capability-dedup-1")
    runtime = IncidentWorkflowRuntime(
        db,
        workflow,
        DeterministicInvestigator(),
        action_service(),
        fixture_capabilities(),
    )

    first = runtime.collect_context([])
    second = runtime.collect_context([])

    assert second == first
    incident = runtime.incidents._require(incident_id)
    assert len(incident.evidence) == 4
    assert {item.evidence_type for item in incident.evidence} == {
        EvidenceType.METRIC,
        EvidenceType.LOG,
        EvidenceType.TICKET,
        EvidenceType.SERVICE_STATUS,
    }
    assert all(item.fingerprint for item in incident.evidence)
    assert all(item.source_reference for item in incident.evidence)


def test_partial_capability_failure_is_audited_and_other_evidence_survives(
    db: Session,
) -> None:
    incident_id = create_incident(db)
    capabilities = fixture_capabilities(metrics=FailingMetrics())
    service = WorkflowService(db, capabilities=capabilities)
    workflow = service.start(incident_id, "operator", "partial-capability-1")
    runtime = IncidentWorkflowRuntime(
        db, workflow, DeterministicInvestigator(), action_service(), capabilities
    )

    evidence_ids = runtime.collect_context([])

    assert len(evidence_ids) == 3
    events = service.runs.list_audit_events(workflow.id)
    degraded = [
        item
        for item in events
        if item.event_type is AuditEventType.WORKFLOW_NODE_COMPLETED
        and item.event_metadata.get("result_status") == "CAPABILITY_UNAVAILABLE"
    ]
    assert len(degraded) == 1
    assert degraded[0].event_metadata["source"] == "metrics"


def test_workflow_actively_investigates_and_stops_at_approval(db: Session) -> None:
    incident_id = create_incident(db)
    service = WorkflowService(
        db,
        action_service=action_service(),
        capabilities=fixture_capabilities(),
    )

    result = service.run(service.start(incident_id, "operator", "active-investigation-1").id)

    assert result.status is WorkflowRunStatus.WAITING
    assert result.current_node == "approval_required"
    assert result.execution_task_id is None
    stored = service.runs.get(result.id)
    assert stored is not None
    collected = IncidentService(db)._require(incident_id).evidence
    assert len(collected) == 4
    assert result.diagnosis_id is not None
def test_capability_timeout_does_not_cancel_other_results() -> None:
    class SlowMetrics:
        async def query(self, query: MetricQuery) -> MetricObservation:
            del query
            await asyncio.sleep(0.05)
            raise AssertionError("timeout should cancel this coroutine")

    capabilities = IncidentCapabilities(
        policy=CapabilityQueryPolicy(allowed_services=frozenset({"mock-service"})),
        metrics=SlowMetrics(),
        health=FixtureHealth(),
        timeout_seconds=0.001,
    )
    result = asyncio.run(capabilities.collect("mock-service", "test", now=NOW))
    assert [item.evidence_type for item in result.evidence] == [EvidenceType.SERVICE_STATUS]
    assert result.failures[0].code == "CAPABILITY_TIMEOUT"
