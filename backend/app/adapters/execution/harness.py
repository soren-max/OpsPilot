from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Protocol

import httpx
import yaml  # type: ignore[import-untyped]
from opentelemetry import trace
from opentelemetry.propagate import inject

from app.domain.actions.models import ActionRequest, ActionType, RiskLevel, TargetEnvironment
from app.domain.execution import (
    BackendType,
    ExecutionBackendDescriptor,
    ExecutionContext,
    ExecutionMode,
    ExecutionPreview,
    ExecutionStatus,
    ExecutionSubmission,
    ReconciliationResult,
)
from app.execution.errors import (
    BackendUnavailable,
    IndeterminateDispatch,
    MalformedBackendResponse,
)

tracer = trace.get_tracer("opspilot.execution.harness")


class HarnessHttpClient(Protocol):
    async def post(self, path: str, *, params: Mapping[str, str], body: str) -> object: ...

    async def get(self, path: str, *, params: Mapping[str, str]) -> object: ...


class HttpxHarnessClient:
    def __init__(
        self,
        base_url: str,
        api_key: str,
        *,
        timeout_seconds: float = 15,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout_seconds
        self.transport = transport

    async def post(self, path: str, *, params: Mapping[str, str], body: str) -> object:
        try:
            headers = {"x-api-key": self.api_key}
            inject(headers)
            async with httpx.AsyncClient(
                base_url=self.base_url,
                headers=headers,
                timeout=self.timeout,
                transport=self.transport,
            ) as client:
                response = await client.post(
                    path,
                    params=params,
                    content=body,
                    headers={"Content-Type": "application/yaml"},
                )
                response.raise_for_status()
                return response.json()
        except httpx.TimeoutException as exc:
            raise IndeterminateDispatch(
                "Harness dispatch timed out; remote acceptance is unknown"
            ) from exc
        except httpx.HTTPError as exc:
            raise BackendUnavailable("Harness dispatch failed before confirmation") from exc
        except ValueError as exc:
            raise MalformedBackendResponse("Harness returned invalid JSON") from exc

    async def get(self, path: str, *, params: Mapping[str, str]) -> object:
        try:
            headers = {"x-api-key": self.api_key}
            inject(headers)
            async with httpx.AsyncClient(
                base_url=self.base_url,
                headers=headers,
                timeout=self.timeout,
                transport=self.transport,
            ) as client:
                response = await client.get(path, params=params)
                response.raise_for_status()
                return response.json()
        except httpx.TimeoutException as exc:
            raise BackendUnavailable("Harness status request timed out") from exc
        except httpx.HTTPError as exc:
            raise BackendUnavailable("Harness status endpoint is unavailable") from exc
        except ValueError as exc:
            raise MalformedBackendResponse("Harness returned invalid JSON") from exc


class HarnessPipelineExecutionBackend:
    descriptor = ExecutionBackendDescriptor(
        backend_type=BackendType.HARNESS,
        supported_action_types=frozenset({ActionType.RESTART_SERVICE}),
        supported_modes=frozenset({ExecutionMode.REMEDIATE, ExecutionMode.CHANGE}),
        supported_environments=frozenset({TargetEnvironment.TEST, TargetEnvironment.PRODUCTION}),
        supports_async=True,
        supports_status=True,
        supports_cancel=False,
        supports_reconciliation=True,
        max_risk_level=RiskLevel.HIGH,
    )

    def __init__(
        self,
        client: HarnessHttpClient,
        *,
        account_id: str,
        org_id: str,
        project_id: str,
    ) -> None:
        self.client = client
        self.account_id = account_id
        self.org_id = org_id
        self.project_id = project_id

    async def prepare(self, request: ActionRequest, context: ExecutionContext) -> ExecutionPreview:
        pipeline = self._pipeline(context)
        return ExecutionPreview(
            backend_type=BackendType.HARNESS,
            profile_name=context.profile.name,
            operation=f"execute allowlisted Harness pipeline {pipeline}",
            changes_state=True,
        )

    async def submit(
        self, request: ActionRequest, context: ExecutionContext
    ) -> ExecutionSubmission:
        pipeline = self._pipeline(context)
        payload = self._runtime_inputs(request, context, pipeline)
        with tracer.start_as_current_span("cicd.pipeline.run") as span:
            span.set_attribute("execution.id", context.execution_id)
            span.set_attribute("backend.type", BackendType.HARNESS.value)
            span.set_attribute("cicd.pipeline.name", pipeline)
            try:
                response = await self.client.post(
                    f"/pipeline/api/pipeline/execute/{pipeline}",
                    params=self._params(),
                    body=payload,
                )
                provider_id = self._provider_execution_id(response)
            except MalformedBackendResponse as exc:
                raise IndeterminateDispatch(
                    "Harness may have accepted dispatch but returned no usable execution ID"
                ) from exc
        return ExecutionSubmission(
            execution_id=context.execution_id,
            backend_type=BackendType.HARNESS,
            backend_execution_id=provider_id,
            submitted_at=datetime.now(UTC),
            initial_status=ExecutionStatus.SUBMITTED,
            safe_provider_status="SUBMITTED",
        )

    async def get_status(self, context: ExecutionContext) -> ReconciliationResult:
        provider_id = context.profile.immutable_refs.get("provider_execution_id")
        if not provider_id:
            return ReconciliationResult(
                execution_id=context.execution_id,
                status=ExecutionStatus.RECONCILIATION_REQUIRED,
                reconciled_at=datetime.now(UTC),
                safe_message="Harness execution ID is not attached",
            )
        response = await self.client.get(
            f"/pipeline/api/pipelines/execution/{provider_id}", params=self._params()
        )
        raw_status = self._raw_status(response)
        return ReconciliationResult(
            execution_id=context.execution_id,
            backend_execution_id=provider_id,
            status=map_harness_status(raw_status),
            reconciled_at=datetime.now(UTC),
            safe_provider_status=raw_status[:80],
        )

    async def reconcile(self, context: ExecutionContext) -> ReconciliationResult:
        return await self.get_status(context)

    def _params(self) -> dict[str, str]:
        return {
            "accountIdentifier": self.account_id,
            "orgIdentifier": self.org_id,
            "projectIdentifier": self.project_id,
            "moduleType": "CD",
        }

    @staticmethod
    def _pipeline(context: ExecutionContext) -> str:
        pipeline = context.profile.immutable_refs.get("pipeline_identifier")
        if not pipeline or not pipeline.replace("_", "").replace("-", "").isalnum():
            raise ValueError("Harness profile requires a safe allowlisted pipeline identifier")
        return pipeline

    def _runtime_inputs(
        self, request: ActionRequest, context: ExecutionContext, pipeline: str
    ) -> str:
        service = getattr(request.parameters, "service", request.target)
        payload = {
            "inputSet": {
                "identifier": f"opspilot_{context.execution_id.replace('-', '')[:20]}",
                "orgIdentifier": self.org_id,
                "projectIdentifier": self.project_id,
                "pipeline": {
                    "identifier": pipeline,
                    "variables": [
                        {"name": "service", "type": "String", "value": service},
                        {
                            "name": "environment",
                            "type": "String",
                            "value": request.environment.value,
                        },
                        {"name": "target", "type": "String", "value": request.target},
                        {"name": "incident_id", "type": "String", "value": context.incident_id},
                        {"name": "execution_id", "type": "String", "value": context.execution_id},
                    ],
                },
            }
        }
        return yaml.safe_dump(payload, sort_keys=True)

    @staticmethod
    def _provider_execution_id(response: object) -> str:
        if not isinstance(response, dict):
            raise MalformedBackendResponse("Harness trigger response must be an object")
        data = response.get("data")
        if isinstance(data, dict):
            plan = data.get("planExecution")
            if isinstance(plan, dict) and isinstance(plan.get("uuid"), str):
                return str(plan["uuid"])[:160]
            if isinstance(data.get("uuid"), str):
                return str(data["uuid"])[:160]
        raise MalformedBackendResponse("Harness trigger response omitted execution ID")

    @staticmethod
    def _raw_status(response: object) -> str:
        if not isinstance(response, dict):
            raise MalformedBackendResponse("Harness status response must be an object")
        data = response.get("data")
        if isinstance(data, dict):
            summary = data.get("pipelineExecutionSummary")
            if isinstance(summary, dict) and isinstance(summary.get("status"), str):
                return str(summary["status"])
            if isinstance(data.get("status"), str):
                return str(data["status"])
        raise MalformedBackendResponse("Harness status response omitted status")


def map_harness_status(status: str) -> ExecutionStatus:
    normalized = status.upper()
    if normalized in {"QUEUED", "WAITING", "ASYNCWAITING"}:
        return ExecutionStatus.QUEUED
    if normalized in {"RUNNING", "TASK_RUNNING", "PAUSED"}:
        return ExecutionStatus.RUNNING
    if normalized in {"SUCCESS", "SUCCEEDED"}:
        return ExecutionStatus.SUCCEEDED
    if normalized in {"FAILED", "ERROR", "EXPIRED"}:
        return ExecutionStatus.FAILED
    if normalized in {"ABORTED", "CANCELLED", "ERRORED"}:
        return ExecutionStatus.CANCELLED
    return ExecutionStatus.UNKNOWN
