from datetime import UTC, datetime
from pathlib import Path

import pytest
from sqlalchemy.orm import Session

from app.domain.execution import (
    BackendType,
    ExecutionContext,
    ExecutionStatus,
    ExecutionSubmission,
)
from app.evaluation.portfolio import (
    CategoryStatus,
    PortfolioArtifact,
    investigation_category,
    mcp_category,
    render_markdown,
    retrieval_category,
)
from app.execution.service import ExecutionDispatcher
from app.repositories.execution_models import ExecutionRecord, OutboxStatus
from tests.execution.test_outbox_and_reconciliation import seed_execution


class KnownFailureBackend:
    async def prepare(self, request: object, context: object) -> object:
        raise AssertionError("not used")

    async def submit(self, request: object, context: object) -> object:
        raise TimeoutError("provider was unreachable before a submission was accepted")

    async def get_status(self, context: object) -> object:
        raise AssertionError("terminal failure is not reconciled")

    async def reconcile(self, context: object) -> object:
        raise AssertionError("terminal failure is not reconciled")


@pytest.mark.asyncio
async def test_known_dispatch_failure_is_terminal(db: Session) -> None:
    execution, outbox, profile = seed_execution(db)
    dispatcher = ExecutionDispatcher(
        db,
        profiles=(profile,),
        backends={BackendType.HARNESS.value: KnownFailureBackend()},  # type: ignore[dict-item]
    )

    assert await dispatcher.dispatch_one()
    db.refresh(execution)
    db.refresh(outbox)
    assert execution.status is ExecutionStatus.FAILED
    assert execution.failure_category == "DISPATCH_FAILED"
    assert outbox.status is OutboxStatus.COMPLETED


class SuccessfulBackend(KnownFailureBackend):
    async def submit(
        self, request: object, context: ExecutionContext
    ) -> ExecutionSubmission:
        return ExecutionSubmission(
            execution_id=context.execution_id,
            backend_type=BackendType.HARNESS,
            backend_execution_id="fixture-run-1",
            submitted_at=datetime.now(UTC),
            initial_status=ExecutionStatus.SUCCEEDED,
            safe_provider_status="SUCCESS",
        )


class FailedVerifier:
    async def verify(self, execution: ExecutionRecord) -> bool:
        return False


@pytest.mark.asyncio
async def test_provider_success_does_not_override_failed_verification(db: Session) -> None:
    execution, outbox, profile = seed_execution(db)
    dispatcher = ExecutionDispatcher(
        db,
        profiles=(profile,),
        backends={BackendType.HARNESS.value: SuccessfulBackend()},  # type: ignore[dict-item]
        verifier=FailedVerifier(),
    )

    assert await dispatcher.dispatch_one()
    db.refresh(execution)
    db.refresh(outbox)
    assert execution.status is ExecutionStatus.SUCCEEDED
    assert execution.verification_status == "FAILED"
    assert outbox.status is OutboxStatus.COMPLETED


def test_offline_categories_recompute_real_datasets() -> None:
    investigation = investigation_category()
    retrieval = retrieval_category()
    mcp = mcp_category()

    assert investigation.metrics["case_count"] == 6
    assert investigation.metrics["llm_investigator"] == "NOT RUN"
    assert retrieval.metrics["document_count"] == 40
    assert retrieval.metrics["query_count"] >= 10  # type: ignore[operator]
    assert retrieval.metrics["hybrid_rrf.recall_at_10"] >= 0.9  # type: ignore[operator]
    assert mcp.status is CategoryStatus.PASS
    assert all(value == 1.0 for value in mcp.metrics.values())


def test_generated_artifact_schema_and_markdown() -> None:
    fixture = Path(__file__).parents[3] / "artifacts/portfolio-benchmark.json"
    if not fixture.exists():
        pytest.skip("generated artifact is created by make portfolio-benchmark")
    artifact = PortfolioArtifact.model_validate_json(fixture.read_text(encoding="utf-8"))
    assert artifact.schema_version == "1.0.0"
    assert set(artifact.categories) >= {
        "incident_investigation",
        "retrieval",
        "safety",
        "workflow_reliability",
        "execution_reliability",
        "mcp_contract",
        "demo_reproducibility",
    }
    rendered = render_markdown(artifact)
    assert artifact.provenance.git_commit in rendered
    assert "NOT RUN" in rendered
