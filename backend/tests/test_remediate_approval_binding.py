from datetime import UTC, datetime

import pytest
from langgraph.checkpoint.memory import InMemorySaver
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.ai.models import InvestigationModelOutput
from app.application.approval_service import ApprovalService
from app.application.incident_service import IncidentService
from app.application.workflow_service import WorkflowService
from app.domain.actions.models import (
    ActionRequest,
    ActionType,
    RiskLevel,
    ServiceActionParams,
    TargetEnvironment,
    UnknownEnvironment,
    resolve_target_environment,
)
from app.domain.actions.policy import ActionPolicyEngine
from app.domain.approvals import ApprovalActor
from app.domain.execution import (
    BackendType,
    ExecutionBackendDescriptor,
    ExecutionContext,
    ExecutionMode,
    ExecutionProfile,
    ExecutionStatus,
    ExecutionSubmission,
)
from app.execution.binding import (
    DISPATCH_EXECUTION_PLANE,
    PROPOSAL_VERSION,
    binding_digest,
    execution_binding,
)
from app.execution.router import ExecutionRouter
from app.execution.service import ExecutionDispatcher, ExecutionPlaneService
from app.repositories.approval_models import ApprovalRequestRecord
from app.repositories.execution_models import ExecutionRecord
from app.repositories.workflow_models import WorkflowRunStatus
from app.schemas_approvals import ApprovalDecisionCreate
from tests.workflows.test_incident_workflow import create_incident, mock_action_service

PROFILE = ExecutionProfile(
    name="test-harness",
    backend_type=BackendType.HARNESS,
    environment=TargetEnvironment.TEST,
    allowed_action_types=frozenset({ActionType.RESTART_SERVICE}),
)
PRODUCTION_PROFILE = ExecutionProfile(
    name="production-harness",
    backend_type=BackendType.HARNESS,
    environment=TargetEnvironment.PRODUCTION,
    allowed_action_types=frozenset({ActionType.RESTART_SERVICE}),
)


def action_request(**changes: object) -> ActionRequest:
    values: dict[str, object] = {
        "action_type": ActionType.RESTART_SERVICE,
        "target": "mock-service",
        "environment": TargetEnvironment.TEST,
        "parameters": ServiceActionParams(service="mock-service"),
        "reason": "Incident workflow proposal",
    }
    values.update(changes)
    return ActionRequest.model_validate(values)


def plane_binding(**changes: object) -> dict[str, object]:
    values: dict[str, object] = {
        "dispatch": DISPATCH_EXECUTION_PLANE,
        "backend_type": BackendType.HARNESS.value,
        "profile_name": PROFILE.name,
        "profile_config": {"name": PROFILE.name, "environment": "test"},
    }
    values.update(changes)
    return execution_binding(action_request(), **values)  # type: ignore[arg-type]


def test_identical_requests_hash_identically() -> None:
    assert binding_digest(plane_binding()) == binding_digest(plane_binding())


def test_key_ordering_does_not_change_the_digest() -> None:
    binding = plane_binding()
    reordered = {key: binding[key] for key in reversed(list(binding))}

    assert binding_digest(binding) == binding_digest(reordered)


def test_explanation_prose_is_not_bound() -> None:
    first = binding_digest(
        execution_binding(
            action_request(reason="Because evidence says so"), dispatch="action_service"
        )
    )
    second = binding_digest(
        execution_binding(
            action_request(reason="Reworded explanation"), dispatch="action_service"
        )
    )

    assert first == second


@pytest.mark.parametrize(
    "changes",
    [
        {"target": "other-service"},
        {"environment": TargetEnvironment.PRODUCTION},
        {"action_type": ActionType.STOP_SERVICE},
        {"parameters": ServiceActionParams(service="other-service")},
    ],
)
def test_mutating_the_execution_request_changes_the_digest(changes: dict[str, object]) -> None:
    baseline = binding_digest(
        execution_binding(action_request(), dispatch="action_service")
    )
    mutated = binding_digest(
        execution_binding(action_request(**changes), dispatch="action_service")
    )

    assert baseline != mutated


@pytest.mark.parametrize(
    "changes",
    [
        {"profile_name": "other-profile"},
        {"backend_type": BackendType.MOCK.value},
        {"profile_config": {"name": "test-harness", "environment": "production"}},
        {"dispatch": "action_service"},
    ],
)
def test_mutating_the_execution_profile_changes_the_digest(changes: dict[str, object]) -> None:
    assert binding_digest(plane_binding()) != binding_digest(plane_binding(**changes))


def test_proposal_version_is_bound() -> None:
    binding = plane_binding()
    assert binding["proposal_version"] == PROPOSAL_VERSION

    bumped = {**binding, "proposal_version": "999"}
    assert binding_digest(binding) != binding_digest(bumped)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("test", TargetEnvironment.TEST),
        ("test-mock", TargetEnvironment.TEST),
        ("production", TargetEnvironment.PRODUCTION),
        ("prod", TargetEnvironment.PRODUCTION),
        ("development", TargetEnvironment.DEVELOPMENT),
        ("lab", TargetEnvironment.DEVELOPMENT),
    ],
)
def test_known_environments_resolve_explicitly(value: str, expected: TargetEnvironment) -> None:
    assert resolve_target_environment(value) is expected


@pytest.mark.parametrize("value", ["gremlin", "", "prod-2", "TEST-2"])
def test_unknown_environments_fail_closed(value: str) -> None:
    with pytest.raises(UnknownEnvironment):
        resolve_target_environment(value)


def test_external_approval_input_cannot_name_an_actor_or_profile() -> None:
    assert set(ApprovalDecisionCreate.model_fields) == {"reason"}
    fields = set(InvestigationModelOutput.model_fields)
    assert not fields & {"actor", "actor_id", "role", "profile", "backend", "approval_id"}


class CountingBackend:
    descriptor = ExecutionBackendDescriptor(
        backend_type=BackendType.HARNESS,
        supported_action_types=frozenset({ActionType.RESTART_SERVICE}),
        supported_modes=frozenset({ExecutionMode.REMEDIATE}),
        supported_environments=frozenset({TargetEnvironment.TEST, TargetEnvironment.PRODUCTION}),
        supports_async=True,
        supports_status=True,
        supports_cancel=False,
        supports_reconciliation=True,
        max_risk_level=RiskLevel.HIGH,
    )

    def __init__(self) -> None:
        self.submit_calls = 0

    async def prepare(self, request: object, context: object) -> object:
        raise AssertionError("prepare is not part of dispatch")

    async def submit(self, request: object, context: ExecutionContext) -> ExecutionSubmission:
        self.submit_calls += 1
        return ExecutionSubmission(
            execution_id=context.execution_id,
            backend_type=BackendType.HARNESS,
            backend_execution_id="harness-run-1",
            submitted_at=datetime.now(UTC),
            initial_status=ExecutionStatus.SUCCEEDED,
            safe_provider_status="SUCCESS",
        )


def approved_workflow(
    db: Session, backend: CountingBackend, key: str
) -> tuple[WorkflowService, str, str]:
    incident_id = create_incident(db, "service unavailable")
    router = ExecutionRouter(
        profiles=(PROFILE, PRODUCTION_PROFILE),
        descriptors=(backend.descriptor,),
        routes={
            (ActionType.RESTART_SERVICE.value, TargetEnvironment.TEST.value): PROFILE.name,
            (
                ActionType.RESTART_SERVICE.value,
                TargetEnvironment.PRODUCTION.value,
            ): PRODUCTION_PROFILE.name,
        },
    )
    service = WorkflowService(
        db,
        checkpointer=InMemorySaver(),
        action_service=mock_action_service("mock-service"),
        execution_plane=ExecutionPlaneService(db, router),
        execution_dispatcher=ExecutionDispatcher(
            db,
            profiles=(PROFILE, PRODUCTION_PROFILE),
            backends={BackendType.HARNESS.value: backend},  # type: ignore[dict-item]
        ),
    )
    workflow = service.run(service.start(incident_id, "operator", key).id)
    approval_id = str(workflow.state_references["approval_id"])
    ApprovalService(db).approve(
        approval_id,
        ApprovalActor(actor_id="operator-2", display_name="Operator Two"),
        "current evidence supports the governed pipeline",
    )
    return service, incident_id, approval_id


def test_approved_unchanged_request_dispatches_once(db: Session) -> None:
    backend = CountingBackend()
    service, _incident_id, approval_id = approved_workflow(db, backend, "binding-happy")

    resumed = service.resume(approval_id)
    service.resume(approval_id)

    assert backend.submit_calls == 1
    assert db.query(ExecutionRecord).count() == 1
    assert db.query(ApprovalRequestRecord).count() == 1
    assert resumed.execution_task_id is not None


@pytest.mark.parametrize(
    ("field", "value"),
    [("service", "different-service"), ("environment", "production")],
)
def test_stale_approval_blocks_dispatch_with_zero_side_effects(
    db: Session, field: str, value: str
) -> None:
    backend = CountingBackend()
    service, incident_id, approval_id = approved_workflow(db, backend, f"binding-stale-{field}")
    incident = IncidentService(db)._require(incident_id)
    setattr(incident, field, value)
    db.commit()

    resumed = service.resume(approval_id)

    assert resumed.status is WorkflowRunStatus.FAILED
    assert "no longer matches" in (resumed.last_error or "")
    # The approval was granted for different content: no external side effect may occur.
    assert backend.submit_calls == 0
    assert db.query(ExecutionRecord).count() == 0


def test_unknown_incident_environment_fails_closed_without_execution(db: Session) -> None:
    backend = CountingBackend()
    service, incident_id, approval_id = approved_workflow(db, backend, "binding-unknown-env")
    incident = IncidentService(db)._require(incident_id)
    incident.environment = "gremlin"
    db.commit()

    resumed = service.resume(approval_id)

    assert resumed.status is WorkflowRunStatus.FAILED
    assert backend.submit_calls == 0
    assert db.query(ExecutionRecord).count() == 0


def test_action_service_route_is_used_only_without_a_governed_plane() -> None:
    binding = execution_binding(action_request(), dispatch="action_service")

    assert binding["dispatch"] == "action_service"
    assert binding["profile_name"] is None
    assert binding["backend_type"] is None


def test_policy_engine_is_the_only_authorization_source() -> None:
    # A model cannot enlarge capability: policy is evaluated from the server-side allowlist.
    engine = ActionPolicyEngine(frozenset({"mock-service"}))
    assert engine.assess(action_request(target="unknown-service")).allowed is False
    with pytest.raises(ValidationError):
        ActionRequest.model_validate(
            {**action_request().model_dump(), "approval_granted": True, "backend": "ansible"}
        )