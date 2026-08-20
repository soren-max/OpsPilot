from sqlalchemy.orm import Session

from app.ai.context import EvidenceContextBuilder
from app.ai.errors import LLMTimeout
from app.ai.guard import EvidenceGroundingValidator, InvestigationGuard
from app.ai.investigator import LLMIncidentInvestigator
from app.ai.models import InvestigationModelOutput, ModelUsage, StructuredReasoningResult
from app.application.workflow_service import WorkflowService
from app.domain.actions.models import ActionType
from app.domain.audit.models import AuditEventType
from app.repositories.workflow_models import WorkflowRunStatus
from tests.workflows.test_incident_workflow import create_incident, mock_action_service


class RecordingProvider:
    provider_name = "fake"
    model_name = "recording-v1"

    def __init__(self, output: InvestigationModelOutput) -> None:
        self.output = output
        self.calls = 0

    async def generate_investigation(self, request: object) -> StructuredReasoningResult:
        del request
        self.calls += 1
        return StructuredReasoningResult(
            output=self.output,
            provider=self.provider_name,
            model=self.model_name,
            prompt_version="1.0",
            latency_ms=12,
            usage=ModelUsage(input_tokens=10, output_tokens=5),
        )


class TimeoutProvider:
    provider_name = "fake"
    model_name = "timeout-v1"

    def __init__(self) -> None:
        self.calls = 0

    async def generate_investigation(self, request: object) -> StructuredReasoningResult:
        del request
        self.calls += 1
        raise LLMTimeout("provider timed out")


def investigator(provider: object, retries: int = 0) -> LLMIncidentInvestigator:
    return LLMIncidentInvestigator(
        provider,  # type: ignore[arg-type]
        EvidenceContextBuilder(),
        InvestigationGuard(EvidenceGroundingValidator(), 0.8),
        max_retries=retries,
    )


def test_grounded_llm_action_still_waits_for_approval(db: Session) -> None:
    incident_id = create_incident(db, "service unavailable")
    # Resolve the durable ID from the context, exactly as the provider would receive it.
    from app.application.incident_service import IncidentService

    stored_evidence_id = IncidentService(db)._require(incident_id).evidence[0].id
    provider = RecordingProvider(
        InvestigationModelOutput(
            statement="The service is unavailable.",
            root_cause="The service process is unavailable.",
            decision_summary="The durable service-status evidence supports restart review.",
            confidence=0.95,
            evidence_ids=(stored_evidence_id,),
            action_type=ActionType.RESTART_SERVICE,
            insufficient_evidence=False,
            uncertainty=None,
        )
    )
    service = WorkflowService(
        db,
        investigator=investigator(provider),
        action_service=mock_action_service("mock-service"),
    )
    result = service.run(service.start(incident_id, "operator", "llm-approval-1").id)

    assert result.status is WorkflowRunStatus.WAITING
    assert result.current_node == "approval_required"
    assert result.execution_task_id is None
    assert result.state_references["investigator_mode"] == "llm"
    assert result.state_references["model"] == "recording-v1"
    assert result.state_references["investigation_evidence_ids"] == [stored_evidence_id]
    events = {item.event_type for item in service.runs.list_audit_events(result.id)}
    assert AuditEventType.LLM_INVESTIGATION_STARTED in events
    assert AuditEventType.LLM_INVESTIGATION_COMPLETED in events


def test_llm_failure_is_explicit_and_never_silently_falls_back(db: Session) -> None:
    incident_id = create_incident(db, "service unavailable")
    provider = TimeoutProvider()
    service = WorkflowService(db, investigator=investigator(provider, retries=1))
    result = service.run(service.start(incident_id, "operator", "llm-timeout-1").id)

    assert result.status is WorkflowRunStatus.FAILED
    assert result.last_error is not None and result.last_error.startswith("LLM_TIMEOUT:")
    assert provider.calls == 2
    events = {item.event_type for item in service.runs.list_audit_events(result.id)}
    assert AuditEventType.LLM_INVESTIGATION_FAILED in events


def test_insufficient_evidence_does_not_force_action_or_resolution(db: Session) -> None:
    incident_id = create_incident(db)
    provider = RecordingProvider(
        InvestigationModelOutput(
            statement="There is not enough evidence to diagnose this incident.",
            root_cause="Unknown due to insufficient evidence.",
            decision_summary="No action is proposed.",
            confidence=0.1,
            evidence_ids=(),
            action_type=None,
            insufficient_evidence=True,
            uncertainty="Metrics, logs, and health evidence are unavailable.",
        )
    )
    service = WorkflowService(db, investigator=investigator(provider))
    result = service.run(service.start(incident_id, "operator", "llm-insufficient-1").id)

    assert result.status is WorkflowRunStatus.SUCCEEDED
    assert result.execution_task_id is None
    assert result.state_references["insufficient_evidence"] is True
