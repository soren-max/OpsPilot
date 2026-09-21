import json
from datetime import UTC, datetime, timedelta

from langgraph.checkpoint.memory import InMemorySaver
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.ai.context import EvidenceContextBuilder
from app.ai.investigator import LLMIncidentInvestigator
from app.ai.models import InvestigationModelOutput, StructuredReasoningResult
from app.ai.prompts import PROMPT_VERSION
from app.application.incident_service import IncidentService
from app.application.replay_service import IncidentReplayService
from app.application.workflow_service import WorkflowService
from app.domain.incidents.evidence import EvidenceType
from app.domain.incidents.memory import KnowledgeQuery, RetrievedKnowledge
from app.repositories.approval_models import ApprovalRequestRecord
from app.repositories.execution_models import ExecutionOutboxRecord, ExecutionRecord
from app.repositories.incident_models import IncidentAuditEventRecord
from app.schemas_incidents import EvidenceCreate
from app.schemas_replay import ReplayRequest
from tests.workflows.test_incident_workflow import create_incident, mock_action_service

NOW = datetime(2026, 9, 21, tzinfo=UTC)


class CapturingProvider:
    """Returns a fixed verdict while recording exactly what the investigator was given."""

    provider_name = "capture"
    model_name = "capture-model"

    def __init__(self) -> None:
        self.requests: list[object] = []

    async def generate_investigation(self, request: object) -> StructuredReasoningResult:
        self.requests.append(request)
        evidence = request.evidence
        return StructuredReasoningResult(
            output=InvestigationModelOutput(
                statement="The available evidence does not justify a mutating action.",
                root_cause="Service process unavailable",
                decision_summary="Current health evidence indicates the process stopped.",
                confidence=0.95,
                evidence_ids=tuple(item.evidence_id for item in evidence[:1]),
                knowledge_refs=(),
                # No action, so the incident stays INVESTIGATING and remains mutable for the
                # late-evidence case.
                action_type=None,
                insufficient_evidence=False,
                uncertainty=None,
            ),
            provider=self.provider_name,
            model=self.model_name,
            prompt_version=PROMPT_VERSION,
            latency_ms=3,
        )


class StubRetriever:
    def __init__(self, records: tuple[RetrievedKnowledge, ...]) -> None:
        self.records = records

    def retrieve(self, query: KnowledgeQuery) -> tuple[RetrievedKnowledge, ...]:
        return self.records


def knowledge(knowledge_id: str) -> RetrievedKnowledge:
    return RetrievedKnowledge(
        knowledge_id=knowledge_id,
        incident_id=f"historical-{knowledge_id}",
        title="Prior restart",
        service="mock-service",
        environment="test-mock",
        root_cause="Process stopped",
        remediation=("restart",),
        verification=("health",),
        retrieval_score=0.7,
        source_reference="/incidents/historical",
        resolved_at=NOW,
    )


def seed_evidence(db: Session, incident_id: str) -> None:
    service = IncidentService(db)
    for index in range(25):
        service.add_evidence(
            incident_id,
            EvidenceCreate(
                evidence_type=EvidenceType.LOG,
                source=f"loki-{index}",
                source_reference=f"https://loki.test/query/{index}",
                summary=f"Log window {index} shows retries",
                excerpt=f"retry attempt {index}",
                observed_at=NOW - timedelta(minutes=index),
                collector="pytest",
            ),
            "tester",
        )
    # Added last so an insertion-order slice of the first N would omit it.
    service.add_evidence(
        incident_id,
        EvidenceCreate(
            evidence_type=EvidenceType.SERVICE_STATUS,
            source="service-health",
            source_reference="https://health.test/mock-service",
            summary="Service mock-service is unavailable.",
            observed_at=NOW - timedelta(hours=1),
            collector="pytest",
        ),
        "tester",
    )


def run_workflow(
    db: Session,
    provider: CapturingProvider,
    retriever: StubRetriever,
    *,
    key: str,
):
    incident_id = create_incident(db)
    seed_evidence(db, incident_id)
    service = WorkflowService(
        db,
        checkpointer=InMemorySaver(),
        investigator=LLMIncidentInvestigator(
            provider,  # type: ignore[arg-type]
            EvidenceContextBuilder(),
            guard=type("G", (), {"validate": staticmethod(lambda output, request: None)})(),  # type: ignore[arg-type]
        ),
        action_service=mock_action_service("mock-service"),
        knowledge_retriever=retriever,
    )
    workflow = service.run(service.start(incident_id, "operator", key).id)
    return incident_id, workflow


def test_frozen_replay_reproduces_the_original_investigator_input(db: Session) -> None:
    provider = CapturingProvider()
    incident_id, workflow = run_workflow(
        db, provider, StubRetriever((knowledge("k-1"),)), key="fidelity"
    )

    original_input_ids = list(workflow.state_references["investigation_input_evidence_ids"])
    snapshot = workflow.state_references["replay_snapshot"]
    frozen_ids = list(snapshot["evidence_ids"])

    # The actual input, not an insertion-order slice that would drop the late health evidence.
    assert original_input_ids == frozen_ids
    assert len(original_input_ids) < 26
    health_ids = [
        item["evidence_id"]
        for item in snapshot["evidence"]
        if item["evidence_type"] == EvidenceType.SERVICE_STATUS.value
    ]
    assert health_ids
    assert health_ids[0] in frozen_ids

    replay = IncidentReplayService(
        db,
        LLMIncidentInvestigator(
            provider,  # type: ignore[arg-type]
            EvidenceContextBuilder(),
            guard=type("G", (), {"validate": staticmethod(lambda output, request: None)})(),  # type: ignore[arg-type]
        ),
    ).replay(incident_id, ReplayRequest(workflow_id=workflow.id, with_historical_memory=False))

    assert replay.frozen_evidence_ids == original_input_ids
    # The provider saw exactly the frozen evidence on both the original run and the replay.
    replayed_input = provider.requests[-1].evidence  # type: ignore[attr-defined]
    assert [item.evidence_id for item in replayed_input] == original_input_ids


def test_evidence_added_after_the_run_does_not_change_the_frozen_replay(db: Session) -> None:
    provider = CapturingProvider()
    incident_id, workflow = run_workflow(
        db, provider, StubRetriever((knowledge("k-1"),)), key="fidelity-late-evidence"
    )
    replay_service = IncidentReplayService(
        db,
        LLMIncidentInvestigator(
            provider,  # type: ignore[arg-type]
            EvidenceContextBuilder(),
            guard=type("G", (), {"validate": staticmethod(lambda output, request: None)})(),  # type: ignore[arg-type]
        ),
    )
    before = replay_service.replay(incident_id, ReplayRequest(workflow_id=workflow.id))

    IncidentService(db).add_evidence(
        incident_id,
        EvidenceCreate(
            evidence_type=EvidenceType.ALERT,
            source="alertmanager",
            source_reference="https://alerts.test/1",
            summary="Brand new alert raised after the workflow finished",
            observed_at=NOW,
            collector="pytest",
        ),
        "tester",
    )

    after = replay_service.replay(incident_id, ReplayRequest(workflow_id=workflow.id))

    assert before.frozen_evidence_ids == after.frozen_evidence_ids
    assert before.replay_diagnosis.root_cause == after.replay_diagnosis.root_cause
    assert after.frozen_evidence_ids == list(
        workflow.state_references["investigation_input_evidence_ids"]
    )


def test_changed_historical_memory_does_not_change_the_frozen_replay(db: Session) -> None:
    provider = CapturingProvider()
    incident_id, workflow = run_workflow(
        db, provider, StubRetriever((knowledge("k-1"),)), key="fidelity-history"
    )

    replay_service = IncidentReplayService(
        db,
        LLMIncidentInvestigator(
            provider,  # type: ignore[arg-type]
            EvidenceContextBuilder(),
            guard=type("G", (), {"validate": staticmethod(lambda output, request: None)})(),  # type: ignore[arg-type]
        ),
    )
    first = replay_service.replay(incident_id, ReplayRequest(workflow_id=workflow.id))
    # A different live memory backend must not change the frozen snapshot.
    swapped = IncidentReplayService(
        db,
        LLMIncidentInvestigator(
            provider,  # type: ignore[arg-type]
            EvidenceContextBuilder(),
            guard=type("G", (), {"validate": staticmethod(lambda output, request: None)})(),  # type: ignore[arg-type]
        ),
    )
    second = swapped.replay(incident_id, ReplayRequest(workflow_id=workflow.id))

    assert first.frozen_historical_incident_ids == ["historical-k-1"]
    assert second.frozen_historical_incident_ids == ["historical-k-1"]


def test_replay_records_its_input_provenance(db: Session) -> None:
    provider = CapturingProvider()
    _incident_id, workflow = run_workflow(
        db, provider, StubRetriever((knowledge("k-1"),)), key="fidelity-provenance"
    )

    snapshot = workflow.state_references["replay_snapshot"]

    assert snapshot["schema_version"] == "2"
    assert snapshot["prompt_version"] == PROMPT_VERSION
    assert snapshot["context_builder"]["schema"] == "evidence-context-1"
    assert snapshot["model_metadata"]["provider"] == "capture"
    assert all(entry["evidence_id"] for entry in snapshot["evidence"])


def test_replay_has_no_side_effects(db: Session) -> None:
    provider = CapturingProvider()
    incident_id, workflow = run_workflow(
        db, provider, StubRetriever((knowledge("k-1"),)), key="fidelity-side-effect"
    )
    before = {
        model: db.scalar(select(func.count()).select_from(model))
        for model in (
            IncidentAuditEventRecord,
            ApprovalRequestRecord,
            ExecutionRecord,
            ExecutionOutboxRecord,
        )
    }

    IncidentReplayService(
        db,
        LLMIncidentInvestigator(
            provider,  # type: ignore[arg-type]
            EvidenceContextBuilder(),
            guard=type("G", (), {"validate": staticmethod(lambda output, request: None)})(),  # type: ignore[arg-type]
        ),
    ).replay(incident_id, ReplayRequest(workflow_id=workflow.id))

    after = {
        model: db.scalar(select(func.count()).select_from(model))
        for model in (
            IncidentAuditEventRecord,
            ApprovalRequestRecord,
            ExecutionRecord,
            ExecutionOutboxRecord,
        )
    }
    assert after == before


def test_frozen_snapshot_is_json_serializable(db: Session) -> None:
    provider = CapturingProvider()
    _incident_id, workflow = run_workflow(
        db, provider, StubRetriever((knowledge("k-1"),)), key="fidelity-json"
    )

    assert json.loads(json.dumps(workflow.state_references["replay_snapshot"])) == (
        workflow.state_references["replay_snapshot"]
    )