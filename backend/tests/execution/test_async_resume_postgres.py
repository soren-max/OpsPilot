"""Real PostgreSQL integration coverage for the execution-resume contract.

CI provisions PostgreSQL and sets ``OPSPILOT_TEST_POSTGRES_URL`` for ``backend/tests/execution``,
so this module exercises the reconciled-resume path on a real transactional database rather than
SQLite. It is skipped when no database is configured (for example on a laptop without Docker).
"""

import os
import uuid

import pytest
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.application.incident_service import IncidentService
from app.application.workflow_service import WorkflowService
from app.db.base import Base
from app.domain.execution import ExecutionStatus
from app.domain.incidents.models import IncidentStatus
from app.execution.service import ExecutionReconciler
from app.repositories.approval_models import ApprovalRequestRecord
from app.repositories.execution_models import ExecutionRecord
from app.repositories.workflow_models import WorkflowRunStatus
from tests.execution.test_async_resume import (
    AsyncHarness,
    HealthyVerifier,
    build_plane,
    start_approved,
)
from tests.workflows.test_incident_workflow import create_incident, mock_action_service

pytestmark = pytest.mark.skipif(
    "OPSPILOT_TEST_POSTGRES_URL" not in os.environ,
    reason="PostgreSQL integration URL is not configured",
)


def sqlalchemy_url(url: str) -> str:
    """Normalize for SQLAlchemy: a bare ``postgresql://`` selects psycopg2, which is not installed.

    This project depends on psycopg 3, so the driver must be named explicitly.
    """

    for prefix in ("postgresql+psycopg://", "postgres+psycopg://"):
        if url.startswith(prefix):
            return url
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+psycopg://", 1)
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+psycopg://", 1)
    return url


def postgres_session() -> tuple[Session, Engine]:
    engine = create_engine(sqlalchemy_url(os.environ["OPSPILOT_TEST_POSTGRES_URL"]))
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False, class_=Session)(), engine


@pytest.mark.asyncio
async def test_reconciled_success_resumes_to_resolution_on_postgres() -> None:
    db, engine = postgres_session()
    try:
        backend = AsyncHarness()
        service, incident_id, workflow_id, approval_id = start_approved(
            db, backend, HealthyVerifier(), key=f"pg-async-{uuid.uuid4().hex}"
        )
        waiting = service.resume(approval_id)
        assert waiting.status is WorkflowRunStatus.WAITING
        execution = db.get(ExecutionRecord, waiting.execution_task_id)
        assert execution is not None
        assert execution.status is ExecutionStatus.SUBMITTED

        await ExecutionReconciler(  # type: ignore[arg-type]
            service.execution_dispatcher  # type: ignore[arg-type]
        ).reconcile(execution.id)
        assert execution.status is ExecutionStatus.SUCCEEDED

        resumed = service.resume_execution(workflow_id)

        assert resumed.status is WorkflowRunStatus.SUCCEEDED
        assert IncidentService(db)._require(incident_id).status is IncidentStatus.RESOLVED
        # Scoped to this workflow: the integration database may hold rows from other tests.
        assert (
            db.query(ApprovalRequestRecord).filter_by(workflow_run_id=workflow_id).count() == 1
        )
        assert backend.submit_calls == 1
        assert db.query(ExecutionRecord).filter_by(workflow_id=workflow_id).count() == 1
    finally:
        db.close()
        engine.dispose()


@pytest.mark.asyncio
async def test_read_only_check_creates_no_execution_record_on_postgres() -> None:
    db, engine = postgres_session()
    try:
        backend = AsyncHarness()
        incident_id = create_incident(db, "read-only-check requested")
        plane, dispatcher = build_plane(db, backend, HealthyVerifier())
        service = WorkflowService(
            db,
            action_service=mock_action_service("mock-service"),
            execution_plane=plane,
            execution_dispatcher=dispatcher,
        )
        workflow = service.start(incident_id, "operator", f"pg-read-only-{uuid.uuid4().hex}")

        result = service.run(workflow.id)

        assert result.status is WorkflowRunStatus.SUCCEEDED
        assert IncidentService(db)._require(incident_id).status is IncidentStatus.RESOLVED
        # No write execution was recorded for this workflow, and the outbox message is only
        # created alongside an execution record.
        assert db.query(ExecutionRecord).filter_by(workflow_id=workflow.id).count() == 0
        assert backend.submit_calls == 0
    finally:
        db.close()
        engine.dispose()