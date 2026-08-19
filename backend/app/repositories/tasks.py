from __future__ import annotations

from datetime import datetime
from typing import Any, cast

from sqlalchemy import select, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.orm import Session, selectinload

from app.core.enums import TaskStatus
from app.models import AuditLog, OperationTarget, OperationTask


class TaskRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def add(self, task: OperationTask) -> OperationTask:
        self.db.add(task)
        self.db.flush()
        return task

    def get(self, task_id: str) -> OperationTask | None:
        return self.db.scalar(
            select(OperationTask)
            .where(OperationTask.id == task_id)
            .options(
                selectinload(OperationTask.targets).selectinload(OperationTarget.service),
                selectinload(OperationTask.targets).selectinload(OperationTarget.host),
            )
        )

    def list_tasks(self, limit: int = 100) -> list[OperationTask]:
        return list(
            self.db.scalars(
                select(OperationTask)
                .options(
                    selectinload(OperationTask.targets).selectinload(OperationTarget.service),
                    selectinload(OperationTask.targets).selectinload(OperationTarget.host),
                )
                .order_by(OperationTask.created_at.desc())
                .limit(limit)
            )
        )

    def claim_next(self, now: datetime) -> OperationTask | None:
        candidate_id = self.db.scalar(
            select(OperationTask.id)
            .where(OperationTask.status == TaskStatus.PENDING)
            .order_by(OperationTask.created_at, OperationTask.id)
            .limit(1)
        )
        if candidate_id is None:
            return None
        result = cast(
            CursorResult[Any],
            self.db.execute(
                update(OperationTask)
                .where(
                    OperationTask.id == candidate_id,
                    OperationTask.status == TaskStatus.PENDING,
                )
                .values(status=TaskStatus.RUNNING, started_at=now, updated_at=now)
            ),
        )
        if result.rowcount != 1:
            self.db.rollback()
            return None
        self.db.commit()
        return self.get(candidate_id)

    def list_audits(self, limit: int = 200) -> list[AuditLog]:
        return list(
            self.db.scalars(select(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit))
        )
