from sqlalchemy.orm import Session

from app.adapters.mcp.contracts import RemediationProposalResult, RemediationToolInput
from app.application import ActionService
from app.application.incident_service import IncidentService
from app.application.workflow_service import WorkflowService
from app.domain.actions.models import (
    ActionRequest,
    ActionType,
    ServiceActionParams,
    TargetEnvironment,
)


class IncidentMcpResourceReader:
    def __init__(self, db: Session) -> None:
        self.service = IncidentService(db)

    def incident(self, incident_id: str) -> dict[str, object]:
        item = self.service._require(incident_id)
        return {
            "incident_id": item.id,
            "title": item.title,
            "summary": item.summary,
            "service": item.service,
            "environment": item.environment,
            "severity": item.severity.value,
            "status": item.status.value,
            "created_at": item.created_at.isoformat(),
            "resolved_at": item.resolved_at.isoformat() if item.resolved_at else None,
        }

    def evidence(self, incident_id: str) -> list[dict[str, object]]:
        item = self.service._require(incident_id)
        return [
            {
                "evidence_id": value.id,
                "type": value.evidence_type.value,
                "source": value.source,
                "source_reference": value.source_reference,
                "summary": value.summary,
                "observed_at": value.observed_at.isoformat(),
            }
            for value in item.evidence
        ]

    def timeline(self, incident_id: str) -> list[dict[str, object]]:
        return [item.model_dump(mode="json") for item in self.service.timeline(incident_id)]

    def knowledge(self, incident_id: str) -> dict[str, object]:
        return self.service.build_knowledge_record(incident_id).model_dump(mode="json")


class WorkflowGovernedActionProposer:
    """Validates ownership then enters the existing durable workflow and approval boundary."""

    def __init__(
        self,
        db: Session,
        workflow_service: WorkflowService,
        action_service: ActionService,
    ) -> None:
        self.db = db
        self.incidents = IncidentService(db)
        self.workflow_service = workflow_service
        self.action_service = action_service

    async def propose(self, request: RemediationToolInput, actor: str) -> RemediationProposalResult:
        incident = self.incidents._require(request.incident_id)
        if request.target != incident.service:
            raise ValueError("Remediation target must match the incident service")
        owned = {item.id for item in incident.evidence}
        if not set(request.evidence_ids).issubset(owned):
            raise ValueError("Evidence references must belong to the incident")
        environment = (
            TargetEnvironment.PRODUCTION
            if incident.environment.lower() in {"production", "prod"}
            else TargetEnvironment.TEST
        )
        action = ActionRequest(
            action_type=ActionType.RESTART_SERVICE,
            target=request.target,
            environment=environment,
            parameters=ServiceActionParams(service=incident.service),
            reason=request.reason,
        )
        assessment = self.action_service.policy.assess(action)
        if not assessment.approval_required:
            raise ValueError("MCP mutating proposals must enter an approval-required policy path")
        key = f"mcp:{request.incident_id}:{request.action_type}:{','.join(request.evidence_ids)}"
        workflow = self.workflow_service.start(request.incident_id, actor, key[:200])
        waiting = self.workflow_service.run(workflow.id)
        approval_id = waiting.state_references.get("approval_id")
        if not isinstance(approval_id, str):
            raise RuntimeError("Workflow did not reach the durable approval boundary")
        return RemediationProposalResult(
            status="approval_required",
            risk_level=assessment.risk_level.value,
            approval_required=True,
            approval_id=approval_id,
            workflow_id=workflow.id,
        )
