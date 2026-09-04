import builtins
from datetime import datetime

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.domain.change import ChangeStatus
from app.repositories.change_models import (
    ChangeOutboxRecord,
    ChangeOutboxStatus,
    ChangeRecord,
)


class ChangeRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def add(self, record: ChangeRecord) -> None:
        self.db.add(record)

    def get(self, change_id: str, *, lock: bool = False) -> ChangeRecord | None:
        query = select(ChangeRecord).where(ChangeRecord.id == change_id)
        if lock:
            query = query.with_for_update()
        return self.db.scalar(query)

    def find_action(self, workflow_id: str, fingerprint: str) -> ChangeRecord | None:
        return self.db.scalar(
            select(ChangeRecord).where(
                ChangeRecord.workflow_id == workflow_id,
                ChangeRecord.action_fingerprint == fingerprint,
            )
        )

    def list(
        self, *, incident_id: str | None = None, limit: int = 100
    ) -> builtins.list[ChangeRecord]:
        query = select(ChangeRecord).order_by(ChangeRecord.created_at.desc()).limit(limit)
        if incident_id:
            query = query.where(ChangeRecord.incident_id == incident_id)
        return builtins.list(self.db.scalars(query))

    def watching(self, *, limit: int = 100) -> builtins.list[ChangeRecord]:
        return builtins.list(
            self.db.scalars(
                select(ChangeRecord)
                .where(
                    or_(
                        ChangeRecord.status.in_(
                            {
                                ChangeStatus.WAITING_REVIEW,
                                ChangeStatus.APPROVED_FOR_MERGE,
                                ChangeStatus.MERGED,
                                ChangeStatus.RECONCILING,
                                ChangeStatus.SYNCED,
                                ChangeStatus.HEALTHY,
                                ChangeStatus.UNKNOWN,
                            }
                        )
                    )
                )
                .order_by(ChangeRecord.updated_at)
                .limit(limit)
            )
        )


class ChangeOutboxRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def add(self, record: ChangeOutboxRecord) -> None:
        self.db.add(record)

    def claim_one(self, *, now: datetime, claimed_until: datetime) -> ChangeOutboxRecord | None:
        item = self.db.scalar(
            select(ChangeOutboxRecord)
            .where(
                ChangeOutboxRecord.available_at <= now,
                ChangeOutboxRecord.status == ChangeOutboxStatus.PENDING,
            )
            .order_by(ChangeOutboxRecord.created_at)
            .with_for_update(skip_locked=True)
            .limit(1)
        )
        if item is not None:
            item.status = ChangeOutboxStatus.CLAIMED
            item.claimed_at = now
            item.claimed_until = claimed_until
            item.attempts += 1
        return item

    def expired_claims(
        self, *, now: datetime, limit: int = 100
    ) -> builtins.list[ChangeOutboxRecord]:
        return builtins.list(
            self.db.scalars(
                select(ChangeOutboxRecord)
                .where(
                    ChangeOutboxRecord.status == ChangeOutboxStatus.CLAIMED,
                    ChangeOutboxRecord.claimed_until < now,
                )
                .order_by(ChangeOutboxRecord.claimed_until)
                .with_for_update(skip_locked=True)
                .limit(limit)
            )
        )
