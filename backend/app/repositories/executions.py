import builtins
from datetime import datetime

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.domain.execution import ExecutionStatus
from app.repositories.execution_models import (
    ExecutionOutboxRecord,
    ExecutionRecord,
    OutboxStatus,
)


class ExecutionRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get(self, execution_id: str, *, lock: bool = False) -> ExecutionRecord | None:
        query = select(ExecutionRecord).where(ExecutionRecord.id == execution_id)
        if lock:
            query = query.with_for_update()
        return self.db.scalar(query)

    def list(self, *, limit: int = 100) -> builtins.list[ExecutionRecord]:
        return builtins.list(
            self.db.scalars(
                select(ExecutionRecord).order_by(ExecutionRecord.created_at.desc()).limit(limit)
            )
        )

    def tracking(self, *, limit: int = 100) -> builtins.list[ExecutionRecord]:
        return builtins.list(
            self.db.scalars(
                select(ExecutionRecord)
                .where(
                    or_(
                        ExecutionRecord.status.in_(
                            {
                                ExecutionStatus.SUBMITTED,
                                ExecutionStatus.RUNNING,
                                ExecutionStatus.UNKNOWN,
                            }
                        ),
                        (
                            (ExecutionRecord.status == ExecutionStatus.QUEUED)
                            & ExecutionRecord.provider_execution_id.is_not(None)
                        ),
                    ),
                )
                .order_by(ExecutionRecord.created_at)
                .limit(limit)
            )
        )

    def add(self, record: ExecutionRecord) -> None:
        self.db.add(record)

    def find_action(self, workflow_id: str, action_fingerprint: str) -> ExecutionRecord | None:
        return self.db.scalar(
            select(ExecutionRecord).where(
                ExecutionRecord.workflow_id == workflow_id,
                ExecutionRecord.action_fingerprint == action_fingerprint,
            )
        )


class ExecutionOutboxRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def add(self, record: ExecutionOutboxRecord) -> None:
        self.db.add(record)

    def claim_one(self, *, now: datetime, claimed_until: datetime) -> ExecutionOutboxRecord | None:
        query = (
            select(ExecutionOutboxRecord)
            .where(
                ExecutionOutboxRecord.available_at <= now,
                ExecutionOutboxRecord.status == OutboxStatus.PENDING,
            )
            .order_by(ExecutionOutboxRecord.created_at)
            .with_for_update(skip_locked=True)
            .limit(1)
        )
        item = self.db.scalar(query)
        if item is not None:
            item.status = OutboxStatus.CLAIMED
            item.claimed_at = now
            item.claimed_until = claimed_until
            item.attempts += 1
        return item
