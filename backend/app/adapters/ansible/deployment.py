from __future__ import annotations

import os
from collections.abc import Mapping
from pathlib import Path
from typing import Protocol

from app.adapters.ansible.runner import AnsibleRunner, SubprocessAnsibleRunner
from app.application.deployment import DeploymentEnvironmentResolver, DeploymentTargetProfile
from app.deployment.config import resolve_operator_path
from app.deployment.models import (
    AnsibleConnectionProfile,
    DeploymentConfiguration,
    DeploymentPreview,
    ServiceControlProfile,
    VerificationCheckType,
)
from app.domain.actions.models import (
    ActionPreview,
    ActionRequest,
    ActionResult,
    ActionStatus,
    ActionType,
    ServiceActionParams,
    VerificationResult,
)

SERVICE_PLAYBOOK = "deployment_service_control.yml"
VERIFICATION_PLAYBOOK = "deployment_verify.yml"


class DeploymentRunnerFactory(Protocol):
    def create(self, connection: AnsibleConnectionProfile) -> AnsibleRunner: ...


class OperatorAnsibleRunnerFactory:
    """Builds SSH-capable Ansible runners exclusively from operator configuration."""

    def __init__(
        self,
        *,
        configuration: DeploymentConfiguration,
        configuration_path: Path,
        playbook_root: Path,
        binary: Path = Path("/usr/bin/ansible-playbook"),
    ) -> None:
        self.configuration = configuration
        self.configuration_path = configuration_path
        self.playbook_root = playbook_root
        self.binary = binary

    def create(self, connection: AnsibleConnectionProfile) -> AnsibleRunner:
        inventory = resolve_operator_path(
            self.configuration_path,
            self.configuration.inventory_catalog[connection.inventory_ref],
        )
        private_key: Path | None = None
        if connection.credential_env_ref:
            value = os.environ.get(connection.credential_env_ref)
            if not value:
                raise RuntimeError("Required Ansible credential reference is unavailable")
            private_key = Path(value).resolve(strict=True)
            if not private_key.is_file():
                raise RuntimeError("Ansible credential reference is not a readable secret file")
        return SubprocessAnsibleRunner(
            inventory=inventory,
            playbook_root=self.playbook_root,
            binary=self.binary,
            timeout_seconds=connection.connection_timeout,
            remote_user=self.configuration.remote_user_catalog[connection.remote_user_ref],
            private_key_file=private_key,
            become_required=connection.become_required,
        )


class DeploymentAnsibleActionExecutor:
    """Resolves semantic actions to fixed playbooks and allowlisted service control values."""

    executor_name = "ansible"

    def __init__(
        self,
        *,
        configuration: DeploymentConfiguration,
        resolver: DeploymentEnvironmentResolver,
        playbook_root: Path,
        runner_factory: DeploymentRunnerFactory,
    ) -> None:
        self.configuration = configuration
        self.resolver = resolver
        self.playbook_root = playbook_root.resolve(strict=True)
        self.runner_factory = runner_factory
        self.connections = {item.id: item for item in configuration.connections}
        self.controls = {item.id: item for item in configuration.service_controls}
        self.verifications = {item.id: item for item in configuration.verifications}

    async def preview(self, action: ActionRequest) -> ActionPreview:
        _, control = self._resolve(action)
        return ActionPreview(
            action_type=action.action_type,
            target=action.target,
            executor=self.executor_name,
            operation=f"{control.control_type.value.lower()}:{action.action_type.value}",
            changes_state=action.action_type
            in {ActionType.START_SERVICE, ActionType.STOP_SERVICE, ActionType.RESTART_SERVICE},
        )

    def deployment_preview(
        self, action: ActionRequest, *, approval_required: bool
    ) -> DeploymentPreview:
        profile, control = self._resolve(action)
        verification = self.verifications[profile.health_profile_ref]
        return DeploymentPreview(
            semantic_action=action.action_type,
            service=profile.service,
            environment=profile.environment.value,
            target_ref=profile.target_ref,
            control_type=control.control_type,
            verification=tuple(
                dict.fromkeys(check.check_type for check in verification.checks)
            ),
            approval_required=approval_required,
        )

    async def execute(self, action: ActionRequest) -> ActionResult:
        profile, control = self._resolve(action)
        connection = self.connections[profile.connection_profile_ref]
        result = await self.runner_factory.create(connection).run(
            playbook=self.playbook_root / SERVICE_PLAYBOOK,
            target=connection.host_alias,
            variables=self._control_variables(action, profile.service, control.id),
        )
        succeeded = result.exit_code == 0
        if not succeeded:
            print(
                "Ansible service control failed:\n"
                f"{result.stdout[-4000:]}\n{result.stderr[-2000:]}",
                flush=True,
            )
        return ActionResult(
            action_type=action.action_type,
            target=action.target,
            status=ActionStatus.SUCCEEDED if succeeded else ActionStatus.FAILED,
            summary=(
                "Bounded Ansible service control completed."
                if succeeded
                else "Bounded Ansible service control failed."
            ),
            executor=self.executor_name,
        )

    async def verify(self, action: ActionRequest) -> VerificationResult:
        profile, _ = self._resolve(action)
        connection = self.connections[profile.connection_profile_ref]
        result = await self.runner_factory.create(connection).run(
            playbook=self.playbook_root / VERIFICATION_PLAYBOOK,
            target=connection.host_alias,
            variables=self._verification_variables(
                profile.health_profile_ref, profile.service, action.action_type
            ),
        )
        verified = result.exit_code == 0
        return VerificationResult(
            action_type=action.action_type,
            target=action.target,
            status=ActionStatus.SUCCEEDED if verified else ActionStatus.FAILED,
            verified=verified,
            summary=(
                "Operator-owned deployment verification passed."
                if verified
                else "Deployment verification failed after execution."
            ),
        )

    def _resolve(
        self, action: ActionRequest
    ) -> tuple[DeploymentTargetProfile, ServiceControlProfile]:
        if not isinstance(action.parameters, ServiceActionParams):
            raise ValueError("Deployment service control requires semantic service parameters")
        profile = self.resolver.resolve(
            service=action.parameters.service,
            environment=action.environment,
            target_ref=action.target,
        )
        if action.action_type not in profile.allowed_actions:
            raise ValueError("Deployment target does not allow this action")
        control = self.controls[profile.service_control_profile_ref]
        if action.action_type not in control.allowed_operations:
            raise ValueError("Service control profile does not allow this operation")
        return profile, control

    def _control_variables(
        self, action: ActionRequest, service: str, control_profile_id: str
    ) -> Mapping[str, str | int]:
        control = self.controls[control_profile_id]
        mapped_service = control.service_mapping[service]
        operation = {
            ActionType.GET_SERVICE_STATUS: "status",
            ActionType.START_SERVICE: "start",
            ActionType.STOP_SERVICE: "stop",
            ActionType.RESTART_SERVICE: "restart",
        }.get(action.action_type)
        if operation is None:
            raise ValueError("Action is not a service control operation")
        systemd_state = {
            "start": "started",
            "stop": "stopped",
            "restart": "restarted",
            "status": "started",
        }[operation]
        return {
            "control_type": control.control_type.value,
            "fixed_operation": operation,
            "fixed_service_id": mapped_service,
            "fixed_script_path": control.fixed_script_path or "/bin/false",
            "fixed_systemd_unit": mapped_service,
            "fixed_systemd_state": systemd_state,
        }

    def _verification_variables(
        self, verification_profile_id: str, service: str, action_type: ActionType
    ) -> Mapping[str, str | int]:
        verification = self.verifications[verification_profile_id]
        applicable = tuple(
            item for item in verification.checks if action_type in item.applicable_actions
        )
        http = next(
            (
                item
                for item in applicable
                if item.check_type is VerificationCheckType.HTTP_HEALTH
            ),
            None,
        )
        systemd = next(
            (
                item
                for item in applicable
                if item.check_type is VerificationCheckType.SYSTEMD_STATUS
            ),
            None,
        )
        process = next(
            (
                item
                for item in applicable
                if item.check_type is VerificationCheckType.PROCESS_STATUS
            ),
            None,
        )
        target = next(
            item
            for item in self.configuration.targets
            if item.health_profile_ref == verification_profile_id and item.service == service
        )
        control = self.controls[target.service_control_profile_ref]
        expected_service_state = (
            systemd.expected_service_state
            if systemd is not None
            else process.expected_service_state
            if process is not None
            else "running"
        )
        return {
            "verify_http": "true" if http else "false",
            "fixed_health_url": (
                self.configuration.endpoint_catalog[http.endpoint_ref]
                if http and http.endpoint_ref
                else "http://127.0.0.1/"
            ),
            "fixed_expected_http_status": (
                http.expected_http_status if http and http.expected_http_status else 200
            ),
            "verify_systemd": "true" if systemd else "false",
            "verify_process": "true" if process else "false",
            "fixed_expected_service_state": expected_service_state or "running",
            "fixed_systemd_unit": control.service_mapping[service],
            "fixed_script_path": control.fixed_script_path or "/bin/false",
            "fixed_service_id": control.service_mapping[service],
            "verification_retries": max(
                1, int(verification.timeout_seconds / verification.retry_interval_seconds)
            ),
            "verification_delay": max(1, int(verification.retry_interval_seconds)),
        }
