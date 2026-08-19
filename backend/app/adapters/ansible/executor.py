from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from app.adapters.ansible.runner import AnsibleRunner
from app.domain.actions.models import (
    ActionPreview,
    ActionRequest,
    ActionResult,
    ActionStatus,
    ActionType,
    HealthCheckParams,
    ServiceActionParams,
    VerificationResult,
)

PLAYBOOK_MAPPING: Mapping[ActionType, str] = {
    ActionType.GET_SERVICE_STATUS: "service_status.yml",
    ActionType.RESTART_SERVICE: "restart_service.yml",
    ActionType.HEALTH_CHECK: "health_check.yml",
}


class AnsibleActionExecutor:
    executor_name = "ansible"

    def __init__(
        self,
        *,
        runner: AnsibleRunner,
        playbook_root: Path,
    ) -> None:
        self.runner = runner
        self.playbook_root = playbook_root.resolve()

    async def preview(self, action: ActionRequest) -> ActionPreview:
        return ActionPreview(
            action_type=action.action_type,
            target=action.target,
            executor=self.executor_name,
            operation=PLAYBOOK_MAPPING[action.action_type],
            changes_state=action.action_type is ActionType.RESTART_SERVICE,
        )

    async def execute(self, action: ActionRequest) -> ActionResult:
        result = await self.runner.run(
            playbook=self._playbook(action.action_type),
            target=action.target,
            variables=self._variables(action),
        )
        succeeded = result.exit_code == 0
        return ActionResult(
            action_type=action.action_type,
            target=action.target,
            status=ActionStatus.SUCCEEDED if succeeded else ActionStatus.FAILED,
            summary="Ansible action completed." if succeeded else "Ansible action failed.",
            executor=self.executor_name,
        )

    async def verify(self, action: ActionRequest) -> VerificationResult:
        verification_action = self._verification_action(action)
        result = await self.runner.run(
            playbook=self._playbook(verification_action.action_type),
            target=verification_action.target,
            variables=self._variables(verification_action),
        )
        verified = result.exit_code == 0
        return VerificationResult(
            action_type=action.action_type,
            target=action.target,
            status=ActionStatus.SUCCEEDED if verified else ActionStatus.FAILED,
            verified=verified,
            summary="Post-action verification passed." if verified else "Verification failed.",
        )

    def _playbook(self, action_type: ActionType) -> Path:
        return self.playbook_root / PLAYBOOK_MAPPING[action_type]

    @staticmethod
    def _variables(action: ActionRequest) -> dict[str, str | int]:
        if isinstance(action.parameters, ServiceActionParams):
            return {"service_name": action.parameters.service}
        if isinstance(action.parameters, HealthCheckParams):
            return {
                "health_port": action.parameters.port,
                "health_path": action.parameters.path,
                "expected_status": action.parameters.expected_status,
            }
        raise TypeError("Unsupported validated action parameters")

    @staticmethod
    def _verification_action(action: ActionRequest) -> ActionRequest:
        if action.action_type is ActionType.RESTART_SERVICE:
            return ActionRequest(
                action_type=ActionType.GET_SERVICE_STATUS,
                target=action.target,
                environment=action.environment,
                parameters=action.parameters,
                reason="Verify that the restarted service is running.",
            )
        return action
