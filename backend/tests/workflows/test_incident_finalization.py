from datetime import UTC, datetime

from langgraph.checkpoint.memory import InMemorySaver
from sqlalchemy.orm import Session

from app.application import ActionService
from app.application.approval_service import ApprovalService
from app.application.incident_service import IncidentService
from app.application.workflow_service import WorkflowService
from app.domain.actions.models import (
    ActionPreview,
    ActionRequest,
    ActionResult,
    ActionStatus,
    ActionType,
    VerificationResult,
)
from app.domain.actions.policy import ActionPolicyEngine
from app.domain.approvals import ApprovalActor
from app.domain.incidents.evidence import EvidenceType
from app.domain.incidents.models import IncidentStatus
from app.repositories.workflow_models import WorkflowRunStatus
from app.schemas_incidents import EvidenceCreate
from app.workflows.incident.investigator import (
    InvestigationContext,
    InvestigationResult,
    InvestigatorMetadata,
)
from tests.workflows.test_incident_workflow import create_incident, mock_action_service

NOW = datetime(2026, 9, 21, tzinfo=UTC)


class StubInvestigator:
    """Investigator with a fixed verdict, used to drive finalize semantics directly."""

    mode = "stub"

    def __init__(
        self,
        *,
        action_type: ActionType | None,
        insufficient_evidence: bool = False,
        confidence: float = 0.9,
    ) -> None:
        self.action_type = action_type
        self.insufficient_evidence = insufficient_evidence
        self.confidence = confidence

    @property
    def metadata(self) -> InvestigatorMetadata:
        return InvestigatorMetadata(mode=self.mode)

    def investigate(self, context: InvestigationContext) -> InvestigationResult:
        return InvestigationResult(
            statement="Stub verdict",
            root_cause="Stub root cause",
            decision_summary="Stub decision",
            confidence=self.confidence,
            evidence_ids=tuple(item.evidence_id for item in context.evidence),
            action_type=self.action_type,
            insufficient_evidence=self.insufficient_evidence,
            input_evidence_ids=tuple(item.evidence_id for item in context.evidence),
        )


class UnverifiedExecutor:
    """Execution reports success but independent verification does not confirm recovery."""

    executor_name = "unverified"

    async def preview(self, action: ActionRequest) -> ActionPreview:
        return ActionPreview(
            action_type=action.action_type,
            target=action.target,
            executor=self.executor_name,
            operation=action.action_type.value,
            changes_state=True,
        )

    async def execute(self, action: ActionRequest) -> ActionResult:
        return ActionResult(
            action_type=action.action_type,
            target=action.target,
            status=ActionStatus.SUCCEEDED,
            summary="Execution reported success.",
            executor=self.executor_name,
        )

    async def verify(self, action: ActionRequest) -> VerificationResult:
        return VerificationResult(
            action_type=action.action_type,
            target=action.target,
            status=ActionStatus.FAILED,
            verified=False,
            summary="Verification could not confirm recovery.",
        )


def add_unhealthy_evidence(db: Session, incident_id: str) -> None:
    IncidentService(db).add_evidence(
        incident_id,
        EvidenceCreate(
            evidence_type=EvidenceType.SERVICE_STATUS,
            source="fixture",
            source_reference="https://example.test/health",
            summary="Service mock-service is unavailable.",
            observed_at=NOW,
            collector="pytest",
        ),
        "tester",
    )


def test_zero_evidence_never_resolves_the_incident(db: Session) -> None:
    incident_id = create_incident(db)
    service = WorkflowService(db, checkpointer=InMemorySaver())
    workflow = service.run(service.start(incident_id, "operator", "finalize-zero").id)

    assert workflow.status is WorkflowRunStatus.SUCCEEDED
    assert IncidentService(db)._require(incident_id).status is IncidentStatus.INVESTIGATING


def test_insufficient_evidence_never_resolves_the_incident(db: Session) -> None:
    incident_id = create_incident(db)
    add_unhealthy_evidence(db, incident_id)
    service = WorkflowService(
        db,
        checkpointer=InMemorySaver(),
        investigator=StubInvestigator(action_type=None, insufficient_evidence=True),
        action_service=mock_action_service("mock-service"),
    )
    workflow = service.run(service.start(incident_id, "operator", "finalize-insufficient").id)

    assert workflow.status is WorkflowRunStatus.SUCCEEDED
    assert IncidentService(db)._require(incident_id).status is IncidentStatus.INVESTIGATING


def test_no_action_against_an_unhealthy_service_never_resolves(db: Session) -> None:
    incident_id = create_incident(db)
    add_unhealthy_evidence(db, incident_id)
    service = WorkflowService(
        db,
        checkpointer=InMemorySaver(),
        investigator=StubInvestigator(action_type=None, insufficient_evidence=False),
        action_service=mock_action_service("mock-service"),
    )
    workflow = service.run(service.start(incident_id, "operator", "finalize-no-action").id)

    assert workflow.status is WorkflowRunStatus.SUCCEEDED
    assert IncidentService(db)._require(incident_id).status is not IncidentStatus.RESOLVED


def test_verified_remediation_resolves_the_incident(db: Session) -> None:
    incident_id = create_incident(db)
    add_unhealthy_evidence(db, incident_id)
    service = WorkflowService(
        db,
        checkpointer=InMemorySaver(),
        investigator=StubInvestigator(action_type=ActionType.RESTART_SERVICE),
        action_service=mock_action_service("mock-service"),
    )
    workflow = service.run(service.start(incident_id, "operator", "finalize-verified").id)
    approval_id = str(workflow.state_references["approval_id"])
    ApprovalService(db).approve(
        approval_id,
        ApprovalActor(actor_id="operator-2", display_name="Operator Two"),
        "current evidence supports the restart",
    )

    resumed = service.resume(approval_id)

    assert resumed.status is WorkflowRunStatus.SUCCEEDED
    assert IncidentService(db)._require(incident_id).status is IncidentStatus.RESOLVED


def test_failed_verification_never_resolves_even_though_execution_succeeded(db: Session) -> None:
    incident_id = create_incident(db)
    add_unhealthy_evidence(db, incident_id)
    service = WorkflowService(
        db,
        checkpointer=InMemorySaver(),
        investigator=StubInvestigator(action_type=ActionType.RESTART_SERVICE),
        action_service=ActionService(
            ActionPolicyEngine(frozenset({"mock-service"})), UnverifiedExecutor()
        ),
    )
    workflow = service.run(service.start(incident_id, "operator", "finalize-verify-failed").id)
    approval_id = str(workflow.state_references["approval_id"])
    ApprovalService(db).approve(
        approval_id,
        ApprovalActor(actor_id="operator-2", display_name="Operator Two"),
        "approved for the bounded restart",
    )

    resumed = service.resume(approval_id)

    assert resumed.status is WorkflowRunStatus.FAILED
    assert IncidentService(db)._require(incident_id).status is not IncidentStatus.RESOLVED


def test_repeated_finalize_is_idempotent(db: Session) -> None:
    incident_id = create_incident(db)
    add_unhealthy_evidence(db, incident_id)
    service = WorkflowService(
        db,
        checkpointer=InMemorySaver(),
        investigator=StubInvestigator(action_type=ActionType.RESTART_SERVICE),
        action_service=mock_action_service("mock-service"),
    )
    workflow = service.run(service.start(incident_id, "operator", "finalize-idempotent").id)
    approval_id = str(workflow.state_references["approval_id"])
    ApprovalService(db).approve(
        approval_id,
        ApprovalActor(actor_id="operator-2", display_name="Operator Two"),
        "approved for the bounded restart",
    )

    first = service.resume(approval_id)
    second = service.resume(approval_id)

    incident = IncidentService(db)._require(incident_id)
    assert first.status is WorkflowRunStatus.SUCCEEDED
    assert second.status is WorkflowRunStatus.SUCCEEDED
    assert incident.status is IncidentStatus.RESOLVED
    assert incident.version == IncidentService(db)._require(incident_id).version