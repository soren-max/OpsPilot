from langgraph.checkpoint.memory import InMemorySaver
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.application.agent_events import AgentEventProjection
from app.application.replay_service import IncidentReplayService
from app.application.workflow_service import WorkflowService
from app.repositories.approval_models import ApprovalRequestRecord
from app.repositories.execution_models import ExecutionOutboxRecord, ExecutionRecord
from app.repositories.incident_models import IncidentAuditEventRecord
from app.schemas_replay import ReplayRequest
from app.workflows.incident.investigator import DeterministicInvestigator
from tests.workflows.test_incident_workflow import create_incident, mock_action_service


def _waiting_workflow(db: Session) -> tuple[str, object]:
    incident_id = create_incident(db, "service unavailable")
    service = WorkflowService(
        db,
        checkpointer=InMemorySaver(),
        action_service=mock_action_service("mock-service"),
    )
    workflow = service.start(incident_id, "operator", "agent-events-replay")
    return incident_id, service.run(workflow.id)


def test_agent_event_projection_is_ordered_staged_and_resumable(db: Session) -> None:
    incident_id, _ = _waiting_workflow(db)

    events = AgentEventProjection(db).list(incident_id)

    assert events == sorted(events, key=lambda item: (item.timestamp, item.event_id))
    assert events[0].event_type == "incident.created"
    assert {item.event_type for item in events} >= {
        "evidence.started",
        "memory.retrieved",
        "grounding.validated",
        "proposal.created",
        "policy.evaluated",
        "approval.requested",
    }
    cursor = events[len(events) // 2].event_id
    resumed = AgentEventProjection(db).list(incident_id, after_event_id=cursor)
    assert resumed == events[len(events) // 2 + 1 :]


def test_agent_event_http_and_sse_share_the_same_durable_projection(
    client: object, db: Session
) -> None:
    incident_id, _ = _waiting_workflow(db)
    expected = client.get(f"/api/v1/incidents/{incident_id}/events").json()["data"]  # type: ignore[attr-defined]

    streamed = client.get(  # type: ignore[attr-defined]
        f"/api/v1/incidents/{incident_id}/events/stream?follow=false"
    )

    assert streamed.status_code == 200
    assert streamed.headers["content-type"].startswith("text/event-stream")
    assert [line[4:] for line in streamed.text.splitlines() if line.startswith("id: ")] == [
        item["event_id"] for item in expected
    ]


def test_frozen_replay_has_no_side_effect_and_reuses_grounding_evaluation(db: Session) -> None:
    incident_id, workflow = _waiting_workflow(db)
    counts_before = {
        model: db.scalar(select(func.count()).select_from(model))
        for model in (
            IncidentAuditEventRecord,
            ApprovalRequestRecord,
            ExecutionRecord,
            ExecutionOutboxRecord,
        )
    }

    result = IncidentReplayService(db, DeterministicInvestigator()).replay(
        incident_id, ReplayRequest(workflow_id=workflow.id)
    )

    assert result.no_side_effect is True
    assert result.frozen_evidence_ids
    assert result.metrics.grounding_valid is True
    assert result.metrics.root_cause_match is True
    assert result.metrics.action_match is True
    assert result.policy.decision == "HUMAN_APPROVAL_REQUIRED"
    assert {
        model: db.scalar(select(func.count()).select_from(model)) for model in counts_before
    } == counts_before
