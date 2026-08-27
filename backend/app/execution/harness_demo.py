"""Explicit opt-in Harness contract demo; never invoked by CI or the application worker."""

import asyncio
import os

from app.adapters.execution.harness import HarnessPipelineExecutionBackend, HttpxHarnessClient
from app.domain.actions.models import (
    ActionRequest,
    ActionType,
    ServiceActionParams,
    TargetEnvironment,
)
from app.domain.execution import BackendType, ExecutionContext, ExecutionProfile


def required(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"{name} is required for the opt-in Harness demo")
    return value


async def run() -> None:
    execution_id = required("OPSPILOT_HARNESS_DEMO_EXECUTION_ID")
    service = required("OPSPILOT_HARNESS_DEMO_SERVICE")
    pipeline = required("OPSPILOT_HARNESS_PIPELINE_IDENTIFIER")
    client = HttpxHarnessClient(
        required("OPSPILOT_HARNESS_BASE_URL"), required("OPSPILOT_HARNESS_API_KEY")
    )
    backend = HarnessPipelineExecutionBackend(
        client,
        account_id=required("OPSPILOT_HARNESS_ACCOUNT_ID"),
        org_id=required("OPSPILOT_HARNESS_ORG_ID"),
        project_id=required("OPSPILOT_HARNESS_PROJECT_ID"),
    )
    request = ActionRequest(
        action_type=ActionType.RESTART_SERVICE,
        target=service,
        environment=TargetEnvironment.PRODUCTION,
        parameters=ServiceActionParams(service=service),
        reason="explicit operator-invoked Harness integration demo",
    )
    context = ExecutionContext(
        execution_id=execution_id,
        incident_id=required("OPSPILOT_HARNESS_DEMO_INCIDENT_ID"),
        workflow_id=required("OPSPILOT_HARNESS_DEMO_WORKFLOW_ID"),
        profile=ExecutionProfile(
            name="manual-harness-demo",
            backend_type=BackendType.HARNESS,
            environment=TargetEnvironment.PRODUCTION,
            allowed_action_types=frozenset({ActionType.RESTART_SERVICE}),
            immutable_refs={"pipeline_identifier": pipeline},
        ),
    )
    preview = await backend.prepare(request, context)
    submission = await backend.submit(request, context)
    print(f"profile={preview.profile_name} execution={submission.execution_id}")
    print(
        f"backend={submission.backend_type.value} provider={submission.backend_execution_id} "
        f"status={submission.initial_status.value}"
    )


if __name__ == "__main__":
    asyncio.run(run())
