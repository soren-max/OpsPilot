from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.adapters.mock import MockActionExecutor
from app.application import ActionService
from app.application.incident_service import IncidentService
from app.application.workflow_service import WorkflowService
from app.domain.actions.policy import ActionPolicyEngine
from app.domain.incidents.evidence import EvidenceType
from app.domain.incidents.memory import KnowledgeQuery, RetrievedKnowledge
from app.domain.incidents.models import Severity
from app.repositories.workflow_models import WorkflowRunStatus
from app.schemas_incidents import EvidenceCreate, IncidentCreate


class HistoricalMemory:
    def __init__(self) -> None:
        self.queries: list[KnowledgeQuery] = []

    def retrieve(self, query: KnowledgeQuery) -> tuple[RetrievedKnowledge, ...]:
        self.queries.append(query)
        return (
            RetrievedKnowledge(
                knowledge_id="knowledge-historical-1",
                incident_id="historical-1",
                title="Previous web process failure",
                service="mock-service",
                environment="test-mock",
                root_cause="Service process unavailable",
                remediation=("restart_service",),
                verification=("health restored",),
                retrieval_score=0.88,
                source_reference="/incidents/historical-1",
                resolved_at=datetime(2026, 8, 19, tzinfo=UTC),
            ),
        )


def test_workflow_retrieves_history_but_action_remains_grounded_in_current_evidence(
    db: Session,
) -> None:
    incidents = IncidentService(db)
    incident = incidents.create_incident(
        IncidentCreate(
            title="Current service-down",
            summary="Current health endpoint is unreachable",
            severity=Severity.HIGH,
            environment="test-mock",
            service="mock-service",
            source="pytest",
        ),
        "tester",
    )
    evidence = incidents.add_evidence(
        incident.id,
        EvidenceCreate(
            evidence_type=EvidenceType.SERVICE_STATUS,
            source="health",
            source_reference="https://example.test/current-health",
            summary="service unavailable",
            observed_at=datetime.now(UTC),
            collector="pytest",
        ),
        "tester",
    )
    memory = HistoricalMemory()
    workflow_service = WorkflowService(
        db,
        action_service=ActionService(
            ActionPolicyEngine(frozenset({"mock-service"})), MockActionExecutor()
        ),
        knowledge_retriever=memory,
    )
    workflow = workflow_service.start(incident.id, "operator", "memory-workflow")
    result = workflow_service.run(workflow.id)

    assert result.status is WorkflowRunStatus.WAITING
    assert memory.queries[0].service == "mock-service"
    assert result.state_references["investigation_evidence_ids"] == [evidence.id]
    assert result.state_references["investigation_knowledge_refs"] == [
        "knowledge-historical-1"
    ]
    related = result.state_references["retrieved_knowledge_refs"]
    assert isinstance(related, list)
    assert related == [
        {
            "knowledge_id": "knowledge-historical-1",
            "incident_id": "historical-1",
            "source_reference": "/incidents/historical-1",
        }
    ]
    diagnosis = incidents._require(incident.id).diagnoses[-1]
    assert diagnosis.evidence_ids == [evidence.id]
