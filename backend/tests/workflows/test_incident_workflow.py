import json
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.adapters.mock import MockActionExecutor
from app.application import ActionService
from app.application.incident_service import IncidentService
from app.application.workflow_service import WorkflowService
from app.domain.actions.policy import ActionPolicyEngine
from app.domain.audit.models import AuditEventType
from app.domain.incidents.evidence import EvidenceType
from app.domain.incidents.models import IncidentStatus, Severity
from app.repositories.incident_models import IncidentAuditEventRecord
from app.repositories.workflow_models import WorkflowRunStatus
from app.schemas_incidents import EvidenceCreate, IncidentCreate
from app.workflows.incident.context import IncidentWorkflowRuntime
from app.workflows.incident.graph import incident_graph_builder
from app.workflows.incident.investigator import DeterministicInvestigator
from app.workflows.incident.routing import (
    route_after_diagnosis,
    route_after_risk,
    route_after_verify,
)
from app.workflows.incident.state import initial_state


def create_incident(
    db: Session,
    evidence_summary: str | None = None,
    *,
    target: str = "mock-service",
) -> str:
    service = IncidentService(db)
    incident = service.create_incident(
        IncidentCreate(
            title="Workflow test incident",
            summary="A deterministic test incident",
            severity=Severity.HIGH,
            environment="test-mock",
            service=target,
            source="pytest",
        ),
        "tester",
    )
    if evidence_summary is not None:
        service.add_evidence(
            incident.id,
            EvidenceCreate(
                evidence_type=EvidenceType.SERVICE_STATUS,
                source="fixture",
                source_reference="https://example.test/evidence/1",
                summary=evidence_summary,
                observed_at=datetime.now(UTC),
                collector="pytest",
            ),
            "tester",
        )
    return incident.id


def mock_action_service(*targets: str) -> ActionService:
    return ActionService(ActionPolicyEngine(frozenset(targets)), MockActionExecutor())


def test_graph_topology_is_explicit() -> None:
    graph = incident_graph_builder().compile().get_graph()
    assert set(graph.nodes) >= {
        "load_incident",
        "collect_context",
        "investigate",
        "diagnose",
        "propose_action",
        "assess_risk",
        "approval_required",
        "execute",
        "verify",
        "failure",
        "finalize",
    }
    edges = {(edge.source, edge.target) for edge in graph.edges}
    assert ("load_incident", "collect_context") in edges
    assert ("execute", "verify") in edges
    assert ("approval_required", "__end__") in edges


def test_state_is_json_serializable_and_contains_references_only() -> None:
    state = initial_state("incident-1", "workflow-1")
    assert json.loads(json.dumps(state)) == state
    assert "db" not in state
    assert "session" not in state
    assert "executor" not in state


def test_conditional_routes() -> None:
    state = initial_state("incident-1", "workflow-1")
    assert route_after_diagnosis(state) == "finalize"
    state["action_needed"] = True
    assert route_after_diagnosis(state) == "propose_action"
    state["approval_required"] = True
    assert route_after_risk(state) == "approval_required"
    state["approval_required"] = False
    state["risk_level"] = "forbidden"
    assert route_after_risk(state) == "finalize"
    state["risk_level"] = "read_only"
    assert route_after_risk(state) == "execute"
    state["verification_status"] = "SUCCEEDED"
    assert route_after_verify(state) == "finalize"
    state["verification_status"] = "FAILED"
    assert route_after_verify(state) == "failure"


def test_no_action_workflow_resolves_incident_and_persists_trace(db: Session) -> None:
    incident_id = create_incident(db)
    service = WorkflowService(db)
    workflow = service.start(incident_id, "operator", "no-action-1")

    result = service.run(workflow.id)

    assert result.status is WorkflowRunStatus.SUCCEEDED
    assert result.current_node == "finalize"
    assert IncidentService(db)._require(incident_id).status is IncidentStatus.RESOLVED
    event_types = {item.event_type for item in service.runs.list_audit_events(result.id)}
    assert AuditEventType.WORKFLOW_STARTED in event_types
    assert AuditEventType.WORKFLOW_NODE_STARTED in event_types
    assert AuditEventType.WORKFLOW_NODE_COMPLETED in event_types
    assert AuditEventType.WORKFLOW_COMPLETED in event_types


def test_mutating_workflow_stops_at_approval_boundary(db: Session) -> None:
    incident_id = create_incident(db, "service unavailable")
    service = WorkflowService(db, action_service=mock_action_service("mock-service"))
    workflow = service.start(incident_id, "operator", "approval-1")

    result = service.run(workflow.id)

    assert result.status is WorkflowRunStatus.WAITING
    assert result.current_node == "approval_required"
    assert result.execution_task_id is None
    assert IncidentService(db)._require(incident_id).status is IncidentStatus.INVESTIGATING
    event_types = [item.event_type for item in service.runs.list_audit_events(result.id)]
    assert AuditEventType.WORKFLOW_PAUSED in event_types


def test_missing_action_service_fails_closed_before_execution(db: Session) -> None:
    incident_id = create_incident(db, "read-only-check requested")
    service = WorkflowService(db)
    workflow = service.start(incident_id, "operator", "missing-action-service-1")

    result = service.run(workflow.id)

    assert result.status is WorkflowRunStatus.FAILED
    assert result.execution_task_id is None
    assert result.last_error is not None
    assert result.last_error.startswith("WORKFLOW_INFRASTRUCTURE_FAILURE:")
    assert "operator-configured ActionService" in result.last_error


def test_read_only_workflow_executes_through_action_core(db: Session) -> None:
    incident_id = create_incident(db, "read-only-check requested")
    action_service = ActionService(
        ActionPolicyEngine(frozenset({"mock-service"})), MockActionExecutor()
    )
    service = WorkflowService(db, action_service=action_service)
    workflow = service.start(incident_id, "operator", "read-only-1")

    result = service.run(workflow.id)

    assert result.status is WorkflowRunStatus.SUCCEEDED
    assert result.execution_task_id is not None
    assert result.state_references["verification_status"] == "SUCCEEDED"
    assert IncidentService(db)._require(incident_id).status is IncidentStatus.RESOLVED


def test_forbidden_policy_fails_closed_without_execution(db: Session) -> None:
    incident_id = create_incident(db, "read-only-check requested")
    action_service = ActionService(ActionPolicyEngine(frozenset()), MockActionExecutor())
    service = WorkflowService(db, action_service=action_service)
    workflow = service.start(incident_id, "operator", "forbidden-1")

    result = service.run(workflow.id)

    assert result.status is WorkflowRunStatus.FAILED
    assert result.execution_task_id is None
    assert result.last_error == "POLICY_BLOCKED"
    assert IncidentService(db)._require(incident_id).status is IncidentStatus.FAILED


def test_verification_failure_uses_failure_handler(db: Session) -> None:
    incident_id = create_incident(db, "read-only-check requested")
    executor = MockActionExecutor({("mock-service", "mock-service"): False})
    action_service = ActionService(
        ActionPolicyEngine(frozenset({"mock-service"})), executor
    )
    service = WorkflowService(db, action_service=action_service)
    workflow = service.start(incident_id, "operator", "verification-failure-1")

    result = service.run(workflow.id)

    assert result.status is WorkflowRunStatus.FAILED
    assert result.last_error == "VERIFICATION_FAILED"
    assert IncidentService(db)._require(incident_id).status is IncidentStatus.FAILED


def test_start_and_terminal_replay_are_idempotent(db: Session) -> None:
    incident_id = create_incident(db)
    service = WorkflowService(db)
    first = service.start(incident_id, "operator", "replay-1")
    duplicate = service.start(incident_id, "operator", "replay-1")
    assert duplicate.id == first.id

    service.run(first.id)
    event_count = db.scalar(
        select(func.count())
        .select_from(IncidentAuditEventRecord)
        .where(IncidentAuditEventRecord.correlation_id == first.id)
    )
    hypothesis_count = len(IncidentService(db)._require(incident_id).hypotheses)
    diagnosis_count = len(IncidentService(db)._require(incident_id).diagnoses)

    service.run(first.id)
    assert db.scalar(
        select(func.count())
        .select_from(IncidentAuditEventRecord)
        .where(IncidentAuditEventRecord.correlation_id == first.id)
    ) == event_count
    incident = IncidentService(db)._require(incident_id)
    assert len(incident.hypotheses) == hypothesis_count
    assert len(incident.diagnoses) == diagnosis_count


def test_side_effect_recovery_and_node_audit_are_idempotent(db: Session) -> None:
    incident_id = create_incident(db, "service unavailable")
    service = WorkflowService(db)
    workflow = service.start(incident_id, "operator", "side-effect-replay-1")
    service.run(workflow.id)
    original_hypothesis_id = workflow.hypothesis_id
    assert original_hypothesis_id is not None
    workflow.hypothesis_id = None
    db.commit()

    runtime = IncidentWorkflowRuntime(db, workflow, DeterministicInvestigator())
    result = runtime.investigate([])
    assert runtime.record_hypothesis(result) == original_hypothesis_id
    assert len(IncidentService(db)._require(incident_id).hypotheses) == 1

    runtime.node_started("replay_probe")
    runtime.node_completed("replay_probe", "SUCCEEDED")
    runtime.node_started("replay_probe")
    runtime.node_completed("replay_probe", "SUCCEEDED")
    events = service.runs.list_audit_events(workflow.id)
    assert sum(
        item.event_type is AuditEventType.WORKFLOW_NODE_STARTED
        and item.event_metadata.get("node") == "replay_probe"
        for item in events
    ) == 1
    assert sum(
        item.event_type is AuditEventType.WORKFLOW_NODE_COMPLETED
        and item.event_metadata.get("node") == "replay_probe"
        for item in events
    ) == 1


def test_run_next_claims_persisted_workflow(db: Session) -> None:
    incident_id = create_incident(db)
    service = WorkflowService(db)
    workflow = service.start(incident_id, "operator", "worker-1")
    assert service.run_next() is True
    assert service.get(workflow.id).status is WorkflowRunStatus.SUCCEEDED
    assert service.run_next() is False


def test_evaluation_hook_records_expected_and_actual_outcomes(db: Session) -> None:
    incident_id = create_incident(db)
    service = WorkflowService(db)
    workflow = service.start(incident_id, "operator", "evaluation-1")
    service.run(workflow.id)

    evaluation = service.record_evaluation(workflow.id, "resolved", "resolved")

    assert evaluation.incident_id == incident_id
    assert evaluation.workflow_id == workflow.id
    assert service.evaluations.list_for_workflow(workflow.id) == [evaluation]
