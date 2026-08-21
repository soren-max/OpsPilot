from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.application.incident_service import safe_audit_metadata
from app.core.errors import ConflictError, NotFoundError
from app.db.base import utc_now
from app.domain.approvals import ApprovalActor, ApprovalDecision, ApprovalStatus
from app.domain.audit.models import ActorType, AuditEventType
from app.repositories.approval_models import ApprovalRequestRecord
from app.repositories.approvals import ApprovalRepository
from app.repositories.incident_models import IncidentAuditEventRecord
from app.repositories.incidents import AuditEventRepository
from app.repositories.workflows import WorkflowRunRepository
from app.services.redaction import redact_text


class ApprovalService:
    """Owns approval state transitions; workflow nodes never write approval rows."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.approvals = ApprovalRepository(db)
        self.workflows = WorkflowRunRepository(db)
        self.audits = AuditEventRepository(db)

    def create_request(
        self, incident_id: str, workflow_id: str, action_fingerprint: str
    ) -> ApprovalRequestRecord:
        existing = self.approvals.pending_for_action(workflow_id, action_fingerprint)
        if existing is not None:
            return existing
        item = ApprovalRequestRecord(
            incident_id=incident_id,
            workflow_run_id=workflow_id,
            action_request_id=action_fingerprint,
            action_fingerprint=action_fingerprint,
            status=ApprovalStatus.PENDING,
            requested_at=utc_now(),
        )
        try:
            self.approvals.add(item)
            self.db.flush()
            self._audit(item, AuditEventType.APPROVAL_REQUESTED, "Human approval requested", None)
            self.db.commit()
        except IntegrityError:
            self.db.rollback()
            existing = self.approvals.pending_for_action(workflow_id, action_fingerprint)
            if existing is None:
                raise
            return existing
        return item

    def approve(
        self, approval_id: str, actor: ApprovalActor, reason: str
    ) -> ApprovalRequestRecord:
        return self._resolve(approval_id, actor, reason, ApprovalDecision.APPROVE)

    def reject(
        self, approval_id: str, actor: ApprovalActor, reason: str
    ) -> ApprovalRequestRecord:
        return self._resolve(approval_id, actor, reason, ApprovalDecision.REJECT)

    def get(self, approval_id: str) -> ApprovalRequestRecord:
        item = self.approvals.get(approval_id)
        if item is None:
            raise NotFoundError("Approval request does not exist")
        return item

    def list(self, incident_id: str | None = None) -> list[ApprovalRequestRecord]:
        return self.approvals.list(incident_id=incident_id)

    def is_approved(self, workflow_id: str, action_fingerprint: str) -> bool:
        item = self.approvals.pending_for_action(workflow_id, action_fingerprint)
        return bool(
            item is not None
            and item.status is ApprovalStatus.APPROVED
            and item.decision is ApprovalDecision.APPROVE
        )

    def mark_resumed(self, approval_id: str) -> ApprovalRequestRecord:
        item = self.get(approval_id)
        if item.status not in {ApprovalStatus.APPROVED, ApprovalStatus.REJECTED}:
            raise ConflictError("APPROVAL_PENDING", "Pending approval cannot resume a workflow")
        if item.resumed_at is None:
            item.resumed_at = utc_now()
            self._audit(item, AuditEventType.WORKFLOW_RESUMED, "Workflow resumed", None)
            self.db.commit()
        return item

    def _resolve(
        self,
        approval_id: str,
        actor: ApprovalActor,
        reason: str,
        decision: ApprovalDecision,
    ) -> ApprovalRequestRecord:
        safe_reason = redact_text(reason.strip())
        if not safe_reason:
            raise ValueError("Approval reason is required")
        item = self.approvals.get(approval_id, lock=True)
        if item is None:
            raise NotFoundError("Approval request does not exist")
        if item.status is not ApprovalStatus.PENDING:
            raise ConflictError("APPROVAL_ALREADY_RESOLVED", "Approval request is already resolved")
        workflow = self.workflows.get(item.workflow_run_id)
        if workflow is None or workflow.proposed_action_id != item.action_fingerprint:
            raise ConflictError("APPROVAL_ACTION_MISMATCH", "Approval no longer matches the action")
        item.status = (
            ApprovalStatus.APPROVED
            if decision is ApprovalDecision.APPROVE
            else ApprovalStatus.REJECTED
        )
        item.decision = decision
        item.reason = safe_reason[:1000]
        item.resolved_at = utc_now()
        item.approver_identity = actor.actor_id
        item.approver_display_name = actor.display_name
        item.approver_type = actor.actor_type.value
        event = (
            AuditEventType.APPROVAL_APPROVED
            if decision is ApprovalDecision.APPROVE
            else AuditEventType.APPROVAL_REJECTED
        )
        self._audit(item, event, f"Human approval {decision.value.lower()}d", actor)
        self.db.commit()
        return item

    def _audit(
        self,
        item: ApprovalRequestRecord,
        event_type: AuditEventType,
        summary: str,
        actor: ApprovalActor | None,
    ) -> None:
        self.audits.append(
            IncidentAuditEventRecord(
                incident_id=item.incident_id,
                event_type=event_type,
                actor_type=ActorType.HUMAN if actor else ActorType.SYSTEM,
                actor_id=actor.actor_id if actor else "workflow",
                correlation_id=item.workflow_run_id,
                occurred_at=utc_now(),
                payload_summary=summary,
                event_metadata=safe_audit_metadata(
                    {
                        "workflow_id": item.workflow_run_id,
                        "approval_id": item.id,
                        "actor_id": actor.actor_id if actor else "workflow",
                        "decision": item.decision.value if item.decision else None,
                    }
                ),
            )
        )
