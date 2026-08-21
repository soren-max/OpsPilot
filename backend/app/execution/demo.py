"""Offline governed execution contract demo using Ansible and Harness fixtures."""

import asyncio
from collections.abc import Mapping

from app.adapters.execution.harness import HarnessPipelineExecutionBackend
from app.adapters.execution.legacy import ActionExecutorBackend
from app.adapters.mock import MockActionExecutor
from app.domain.actions.models import (
    ActionRequest,
    ActionType,
    ServiceActionParams,
    TargetEnvironment,
)
from app.domain.actions.policy import ActionPolicyEngine
from app.domain.execution import BackendType, ExecutionBackend, ExecutionContext, ExecutionProfile
from app.execution.router import ExecutionRouter


class FakeHarnessServer:
    async def post(self, path: str, *, params: Mapping[str, str], body: str) -> object:
        del path, params, body
        return {"data": {"planExecution": {"uuid": "fake-harness-run-1"}}}

    async def get(self, path: str, *, params: Mapping[str, str]) -> object:
        del path, params
        return {"data": {"pipelineExecutionSummary": {"status": "Success"}}}


def action(environment: TargetEnvironment) -> ActionRequest:
    return ActionRequest(
        action_type=ActionType.RESTART_SERVICE,
        target="demo-service",
        environment=environment,
        parameters=ServiceActionParams(service="demo-service"),
        reason="current service health evidence reports process unavailable",
    )


async def run() -> None:
    ansible = ActionExecutorBackend(MockActionExecutor(), BackendType.ANSIBLE)
    harness = HarnessPipelineExecutionBackend(
        FakeHarnessServer(), account_id="fixture", org_id="fixture", project_id="fixture"
    )
    lab = ExecutionProfile(
        name="lab-ansible",
        backend_type=BackendType.ANSIBLE,
        environment=TargetEnvironment.TEST,
        allowed_action_types=frozenset({ActionType.RESTART_SERVICE}),
    )
    production = ExecutionProfile(
        name="prod-restart-harness",
        backend_type=BackendType.HARNESS,
        environment=TargetEnvironment.PRODUCTION,
        allowed_action_types=frozenset({ActionType.RESTART_SERVICE}),
        target_mapping={"demo-service": "demo-service"},
        immutable_refs={"pipeline_identifier": "opspilot_restart_service"},
    )
    router = ExecutionRouter(
        profiles=(lab, production),
        descriptors=(ansible.descriptor, harness.descriptor),
        routes={
            (ActionType.RESTART_SERVICE.value, TargetEnvironment.TEST.value): lab.name,
            (
                ActionType.RESTART_SERVICE.value,
                TargetEnvironment.PRODUCTION.value,
            ): production.name,
        },
    )
    policy = ActionPolicyEngine(frozenset({"demo-service"}))
    scenarios: tuple[tuple[ActionRequest, ExecutionBackend], ...] = (
        (action(TargetEnvironment.TEST), ansible),
        (action(TargetEnvironment.PRODUCTION), harness),
    )
    for index, (request, backend) in enumerate(scenarios, start=1):
        assessment = policy.assess(request, approval_granted=True)
        route = router.route(request, assessment)
        profile = lab if route.profile_name == lab.name else production
        context = ExecutionContext(
            execution_id=f"demo-execution-{index}",
            incident_id=f"demo-incident-{index}",
            workflow_id=f"demo-workflow-{index}",
            profile=profile,
        )
        submission = await backend.submit(request, context)
        verification = "CURRENT health verification required"
        print(
            f"Action={request.action_type.value} Policy={assessment.risk_level.value} "
            f"Approval=granted Route={route.profile_name} Backend={route.backend_type.value}"
        )
        print(
            f"Execution={submission.execution_id} Status={submission.initial_status.value} "
            f"Verification={verification}"
        )


if __name__ == "__main__":
    asyncio.run(run())
