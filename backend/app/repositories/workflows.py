from sqlalchemy import select
from sqlalchemy.orm import Session

from app.repositories.incident_models import IncidentAuditEventRecord
from app.repositories.workflow_models import (
    WorkflowEvaluationRecord,
    WorkflowRunRecord,
    WorkflowRunStatus,
)


class WorkflowRunRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get(self, workflow_id: str) -> WorkflowRunRecord | None:
        return self.db.get(WorkflowRunRecord, workflow_id)

    def find_idempotent(
        self, incident_id: str, started_by: str, idempotency_key: str
    ) -> WorkflowRunRecord | None:
        return self.db.scalar(
            select(WorkflowRunRecord).where(
                WorkflowRunRecord.incident_id == incident_id,
                WorkflowRunRecord.started_by == started_by,
                WorkflowRunRecord.idempotency_key == idempotency_key,
            )
        )

    def list_for_incident(self, incident_id: str) -> list[WorkflowRunRecord]:
        return list(
            self.db.scalars(
                select(WorkflowRunRecord)
                .where(WorkflowRunRecord.incident_id == incident_id)
                .order_by(WorkflowRunRecord.created_at.desc())
            )
        )

    def add(self, item: WorkflowRunRecord) -> None:
        self.db.add(item)

    def list_audit_events(self, workflow_id: str) -> list[IncidentAuditEventRecord]:
        return list(
            self.db.scalars(
                select(IncidentAuditEventRecord)
                .where(IncidentAuditEventRecord.correlation_id == workflow_id)
                .order_by(IncidentAuditEventRecord.occurred_at, IncidentAuditEventRecord.event_id)
            )
        )

    def claim_next(self) -> WorkflowRunRecord | None:
        item = self.db.scalar(
            select(WorkflowRunRecord)
            .where(WorkflowRunRecord.status == WorkflowRunStatus.PENDING)
            .order_by(WorkflowRunRecord.created_at)
            .with_for_update(skip_locked=True)
        )
        if item is not None:
            item.status = WorkflowRunStatus.RUNNING
        return item


class WorkflowEvaluationRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def add(self, item: WorkflowEvaluationRecord) -> None:
        self.db.add(item)

    def list_for_workflow(self, workflow_id: str) -> list[WorkflowEvaluationRecord]:
        return list(
            self.db.scalars(
                select(WorkflowEvaluationRecord)
                .where(WorkflowEvaluationRecord.workflow_id == workflow_id)
                .order_by(WorkflowEvaluationRecord.created_at, WorkflowEvaluationRecord.id)
            )
        )
