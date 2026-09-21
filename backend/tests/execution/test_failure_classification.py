import httpx
import pytest
from sqlalchemy.orm import Session

from app.adapters.execution.harness import (
    HarnessPipelineExecutionBackend,
    HttpxHarnessClient,
)
from app.domain.actions.models import (
    ActionRequest,
    ActionType,
    ServiceActionParams,
    TargetEnvironment,
)
from app.domain.execution import (
    BackendType,
    ExecutionContext,
    ExecutionProfile,
    ExecutionStatus,
)
from app.execution.errors import BackendUnavailable, IndeterminateDispatch
from app.execution.service import ExecutionDispatcher
from app.repositories.execution_models import OutboxStatus
from tests.execution.test_outbox_and_reconciliation import seed_execution

URL = "https://harness.example.test"


def client(handler: object) -> HttpxHarnessClient:
    return HttpxHarnessClient(URL, "test-api-key", transport=httpx.MockTransport(handler))  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_connection_refused_before_submission_is_definitely_not_submitted() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    with pytest.raises(BackendUnavailable):
        await client(handler).post("/pipeline", params={}, body="{}")


@pytest.mark.asyncio
async def test_connect_timeout_is_definitely_not_submitted() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectTimeout("connect timed out", request=request)

    with pytest.raises(BackendUnavailable):
        await client(handler).post("/pipeline", params={}, body="{}")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "error",
    [
        httpx.ReadTimeout("read timed out"),
        httpx.WriteError("connection reset while writing"),
        httpx.ReadError("connection reset while reading"),
        httpx.RemoteProtocolError("server disconnected without a response"),
    ],
)
async def test_post_submission_transport_failure_is_indeterminate(error: Exception) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise error

    with pytest.raises(IndeterminateDispatch):
        await client(handler).post("/pipeline", params={}, body="{}")


@pytest.mark.asyncio
async def test_ambiguous_server_error_is_indeterminate() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, request=request, text="upstream unavailable")

    with pytest.raises(IndeterminateDispatch):
        await client(handler).post("/pipeline", params={}, body="{}")


@pytest.mark.asyncio
async def test_rejected_request_is_definitely_not_submitted() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, request=request, text="unauthorized")

    with pytest.raises(BackendUnavailable):
        await client(handler).post("/pipeline", params={}, body="{}")


@pytest.mark.asyncio
async def test_accepted_request_returns_the_remote_handle() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, request=request, json={"data": {"planExecutionId": "run-42"}})

    response = await client(handler).post("/pipeline", params={}, body="{}")

    assert response == {"data": {"planExecutionId": "run-42"}}


@pytest.mark.asyncio
async def test_unparsable_acceptance_response_is_indeterminate() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, request=request, text="<html>not json</html>")

    with pytest.raises(Exception) as caught:
        await client(handler).post("/pipeline", params={}, body="{}")

    # Invalid JSON after a 200 means the pipeline may well have started.
    assert "invalid JSON" in str(caught.value)


PROFILE = ExecutionProfile(
    name="prod-harness",
    backend_type=BackendType.HARNESS,
    environment=TargetEnvironment.PRODUCTION,
    allowed_action_types=frozenset({ActionType.RESTART_SERVICE}),
    target_mapping={"mock-service": "mock-service"},
    immutable_refs={"pipeline_identifier": "restart_service"},
)


def harness_backend(handler: object) -> HarnessPipelineExecutionBackend:
    return HarnessPipelineExecutionBackend(
        HttpxHarnessClient(URL, "test-api-key", transport=httpx.MockTransport(handler)),  # type: ignore[arg-type]
        account_id="account",
        org_id="org",
        project_id="project",
    )


def harness_context() -> ExecutionContext:
    return ExecutionContext(
        execution_id="execution-1",
        incident_id="incident-1",
        workflow_id="workflow-1",
        profile=PROFILE,
    )


def restart_request() -> ActionRequest:
    return ActionRequest(
        action_type=ActionType.RESTART_SERVICE,
        target="mock-service",
        environment=TargetEnvironment.PRODUCTION,
        parameters=ServiceActionParams(service="mock-service"),
        reason="Incident remediation.",
    )


@pytest.mark.asyncio
async def test_missing_remote_handle_is_indeterminate_not_a_clean_failure() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        # Accepted with 200 but no usable execution id.
        return httpx.Response(200, request=request, json={"data": {"status": "ok"}})

    backend = harness_backend(handler)

    with pytest.raises(IndeterminateDispatch):
        await backend.submit(restart_request(), harness_context())


@pytest.mark.asyncio
async def test_known_remote_handle_is_reported_as_submitted() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, request=request, json={"data": {"uuid": "harness-execution-9"}}
        )

    submission = await harness_backend(handler).submit(restart_request(), harness_context())

    assert submission.backend_execution_id == "harness-execution-9"
    assert submission.initial_status is ExecutionStatus.SUBMITTED


class LostResponseBackend:
    """An ambiguous dispatch: the request may have been accepted."""

    def __init__(self) -> None:
        self.submit_calls = 0

    async def submit(self, request: object, context: object) -> object:
        self.submit_calls += 1
        raise IndeterminateDispatch("response lost after the request was written")

    async def get_status(self, context: object) -> object:
        raise AssertionError("manual reconciliation is required; no automatic lookup exists")

    async def reconcile(self, context: object) -> object:
        raise AssertionError("the provider exposes no correlation API")


@pytest.mark.asyncio
async def test_ambiguous_dispatch_is_never_retried_and_requires_manual_reconciliation(
    db: Session,
) -> None:
    execution, outbox, profile = seed_execution(db)
    backend = LostResponseBackend()
    dispatcher = ExecutionDispatcher(
        db,
        profiles=(profile,),
        backends={BackendType.HARNESS.value: backend},  # type: ignore[dict-item]
    )

    assert await dispatcher.dispatch_one()
    db.refresh(execution)
    db.refresh(outbox)

    assert backend.submit_calls == 1
    assert execution.attempt == 1
    assert execution.status is ExecutionStatus.UNKNOWN
    assert execution.failure_category == "INDETERMINATE_DISPATCH"
    # The outbox is NOT returned to PENDING, so dispatch cannot happen twice.
    assert outbox.status is OutboxStatus.INDETERMINATE
