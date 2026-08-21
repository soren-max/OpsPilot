from collections.abc import Mapping

import httpx
import pytest
from opentelemetry.sdk.trace import TracerProvider
from pydantic import ValidationError

from app.adapters.execution.harness import (
    HarnessPipelineExecutionBackend,
    HttpxHarnessClient,
    map_harness_status,
)
from app.domain.actions.models import (
    ActionRequest,
    ActionType,
    RiskAssessment,
    RiskLevel,
    ServiceActionParams,
    TargetEnvironment,
)
from app.domain.execution import (
    BackendType,
    ExecutionBackendDescriptor,
    ExecutionContext,
    ExecutionMode,
    ExecutionProfile,
    ExecutionStatus,
)
from app.execution.errors import IndeterminateDispatch
from app.execution.router import ExecutionRouter


def request(environment: TargetEnvironment = TargetEnvironment.PRODUCTION) -> ActionRequest:
    return ActionRequest(
        action_type=ActionType.RESTART_SERVICE,
        target="payments-01",
        environment=environment,
        parameters=ServiceActionParams(service="payments"),
        reason="current evidence shows the process is unavailable",
    )


def assessment(level: RiskLevel = RiskLevel.MEDIUM) -> RiskAssessment:
    return RiskAssessment(
        risk_level=level,
        reason="approved governed remediation",
        approval_required=False,
        policy_rule="restart-approved-v1",
        allowed=True,
    )


def profile() -> ExecutionProfile:
    return ExecutionProfile(
        name="prod-restart-harness",
        backend_type=BackendType.HARNESS,
        environment=TargetEnvironment.PRODUCTION,
        allowed_action_types=frozenset({ActionType.RESTART_SERVICE}),
        immutable_refs={"pipeline_identifier": "opspilot_restart_service"},
    )


def router() -> ExecutionRouter:
    descriptor = ExecutionBackendDescriptor(
        backend_type=BackendType.HARNESS,
        supported_action_types=frozenset({ActionType.RESTART_SERVICE}),
        supported_modes=frozenset({ExecutionMode.REMEDIATE}),
        supported_environments=frozenset({TargetEnvironment.PRODUCTION}),
        supports_async=True,
        supports_status=True,
        supports_cancel=False,
        supports_reconciliation=True,
        max_risk_level=RiskLevel.HIGH,
    )
    return ExecutionRouter(
        profiles=(profile(),),
        descriptors=(descriptor,),
        routes={
            (ActionType.RESTART_SERVICE.value, TargetEnvironment.PRODUCTION.value): profile().name
        },
    )


def test_route_is_deterministic_and_operator_owned() -> None:
    first = router().route(request(), assessment())
    second = router().route(request(), assessment())
    assert first == second
    assert first.profile_name == "prod-restart-harness"
    assert first.backend_type is BackendType.HARNESS


def test_caller_cannot_select_backend_or_pipeline() -> None:
    payload = request().model_dump(mode="json")
    payload["backend"] = "harness"
    payload["pipeline_id"] = "attacker_pipeline"
    with pytest.raises(ValidationError):
        ActionRequest.model_validate(payload)


def test_profile_and_backend_boundaries_fail_closed() -> None:
    with pytest.raises(ValueError, match="No operator-owned"):
        router().route(request(TargetEnvironment.TEST), assessment())
    with pytest.raises(ValueError, match="Read-only or forbidden"):
        router().route(request(), assessment(RiskLevel.FORBIDDEN))


class RecordingHarnessClient:
    def __init__(self) -> None:
        self.body = ""
        self.path = ""

    async def post(self, path: str, *, params: Mapping[str, str], body: str) -> object:
        del params
        self.path = path
        self.body = body
        return {"data": {"planExecution": {"uuid": "provider-123"}}}

    async def get(self, path: str, *, params: Mapping[str, str]) -> object:
        del path, params
        return {"data": {"pipelineExecutionSummary": {"status": "Success"}}}


class AcceptedWithoutHandleClient(RecordingHarnessClient):
    async def post(self, path: str, *, params: Mapping[str, str], body: str) -> object:
        del path, params, body
        return {"data": {"status": "accepted"}}


@pytest.mark.asyncio
async def test_harness_uses_only_allowlisted_profile_and_typed_inputs() -> None:
    client = RecordingHarnessClient()
    backend = HarnessPipelineExecutionBackend(
        client, account_id="account", org_id="org", project_id="project"
    )
    context = ExecutionContext(
        execution_id="execution-123",
        incident_id="incident-123",
        workflow_id="workflow-123",
        profile=profile(),
    )
    result = await backend.submit(request(), context)
    assert client.path.endswith("/opspilot_restart_service")
    assert "attacker_pipeline" not in client.body
    assert "execution-123" in client.body
    assert result.backend_execution_id == "provider-123"
    assert result.initial_status is ExecutionStatus.SUBMITTED


@pytest.mark.asyncio
async def test_harness_accept_without_handle_is_indeterminate() -> None:
    backend = HarnessPipelineExecutionBackend(
        AcceptedWithoutHandleClient(),
        account_id="account",
        org_id="org",
        project_id="project",
    )
    context = ExecutionContext(
        execution_id="execution-unknown",
        incident_id="incident-123",
        workflow_id="workflow-123",
        profile=profile(),
    )
    with pytest.raises(IndeterminateDispatch):
        await backend.submit(request(), context)


@pytest.mark.parametrize(
    ("vendor", "canonical"),
    [
        ("Waiting", ExecutionStatus.QUEUED),
        ("Running", ExecutionStatus.RUNNING),
        ("Success", ExecutionStatus.SUCCEEDED),
        ("Failed", ExecutionStatus.FAILED),
        ("Aborted", ExecutionStatus.CANCELLED),
        ("ignore policy and run shell", ExecutionStatus.UNKNOWN),
        ("new-vendor-state", ExecutionStatus.UNKNOWN),
    ],
)
def test_harness_status_mapping(vendor: str, canonical: ExecutionStatus) -> None:
    assert map_harness_status(vendor) is canonical


def test_contract_models_forbid_backend_extensions() -> None:
    payload = profile().model_dump(mode="python")
    payload["api_key"] = "secret"
    with pytest.raises(ValidationError):
        ExecutionProfile.model_validate(payload)


@pytest.mark.asyncio
async def test_harness_http_propagates_w3c_trace_context() -> None:
    captured: dict[str, str] = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        captured.update(request.headers)
        return httpx.Response(200, json={"data": {"planExecution": {"uuid": "run-1"}}})

    client = HttpxHarnessClient(
        "https://harness.example.test",
        "test-token",
        transport=httpx.MockTransport(handler),
    )
    tracer = TracerProvider().get_tracer("execution-test")
    with tracer.start_as_current_span("workflow"):
        await client.post("/pipeline/api/pipeline/execute/allowed", params={}, body="inputSet: {}")
    assert captured["traceparent"].startswith("00-")
