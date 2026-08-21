from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.approvals import ApprovalStatus
from app.repositories.approval_models import ApprovalRequestRecord


class ApprovalRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get(self, approval_id: str, *, lock: bool = False) -> ApprovalRequestRecord | None:
        query = select(ApprovalRequestRecord).where(ApprovalRequestRecord.id == approval_id)
        if lock:
            query = query.with_for_update()
        return self.db.scalar(query)

    def pending_for_action(
        self, workflow_id: str, action_fingerprint: str
    ) -> ApprovalRequestRecord | None:
        return self.db.scalar(
            select(ApprovalRequestRecord).where(
                ApprovalRequestRecord.workflow_run_id == workflow_id,
                ApprovalRequestRecord.action_fingerprint == action_fingerprint,
            )
        )

    def list(self, *, incident_id: str | None = None) -> list[ApprovalRequestRecord]:
        query = select(ApprovalRequestRecord)
        if incident_id is not None:
            query = query.where(ApprovalRequestRecord.incident_id == incident_id)
        return list(self.db.scalars(query.order_by(ApprovalRequestRecord.requested_at.desc())))

    def add(self, item: ApprovalRequestRecord) -> None:
        self.db.add(item)

    def count_pending(self, workflow_id: str) -> int:
        return len(
            list(
                self.db.scalars(
                    select(ApprovalRequestRecord.id).where(
                        ApprovalRequestRecord.workflow_run_id == workflow_id,
                        ApprovalRequestRecord.status == ApprovalStatus.PENDING,
                    )
                )
            )
        )
