import asyncio
from collections.abc import Mapping
from pathlib import Path

import pytest

from app.adapters.ansible.deployment import (
    DeploymentAnsibleActionExecutor,
    OperatorAnsibleRunnerFactory,
)
from app.adapters.ansible.runner import AnsibleRunResult
from app.deployment.config import load_deployment_configuration
from app.deployment.resolver import ConfigDeploymentEnvironmentResolver
from app.domain.actions.models import (
    ActionRequest,
    ActionType,
    ServiceActionParams,
    TargetEnvironment,
)

ROOT = Path(__file__).parents[3]
CONFIG_PATH = ROOT / "deployment/examples/legacy-test.yaml"
SYSTEMD_CONFIG_PATH = ROOT / "deployment/examples/systemd-test.yaml"
PLAYBOOK_ROOT = ROOT / "backend/app/deployment/playbooks"


class RecordingRunner:
    def __init__(self) -> None:
        self.calls: list[tuple[Path, str, Mapping[str, str | int]]] = []

    async def run(
        self,
        *,
        playbook: Path,
        target: str,
        variables: Mapping[str, str | int],
    ) -> AnsibleRunResult:
        self.calls.append((playbook, target, variables))
        return AnsibleRunResult(0, "ok", "")


class RecordingFactory:
    def __init__(self, runner: RecordingRunner) -> None:
        self.runner = runner

    def create(self, _connection: object) -> RecordingRunner:
        return self.runner


def action(action_type: ActionType = ActionType.RESTART_SERVICE) -> ActionRequest:
    return ActionRequest(
        action_type=action_type,
        target="demo-api",
        environment=TargetEnvironment.TEST,
        parameters=ServiceActionParams(service="demo-api"),
        reason="Current health evidence shows the service is unavailable.",
    )


def test_fixed_script_uses_only_operator_mapping_and_fixed_playbooks() -> None:
    configuration = load_deployment_configuration(CONFIG_PATH)
    runner = RecordingRunner()
    executor = DeploymentAnsibleActionExecutor(
        configuration=configuration,
        resolver=ConfigDeploymentEnvironmentResolver(configuration),
        playbook_root=PLAYBOOK_ROOT,
        runner_factory=RecordingFactory(runner),  # type: ignore[arg-type]
    )

    result = asyncio.run(executor.execute(action()))
    verification = asyncio.run(executor.verify(action()))

    assert result.status.value == "succeeded"
    assert verification.verified
    assert [call[0].name for call in runner.calls] == [
        "deployment_service_control.yml",
        "deployment_verify.yml",
    ]
    variables = runner.calls[0][2]
    assert variables["fixed_script_path"] == "/opt/opspilot-demo/services.sh"
    assert variables["fixed_operation"] == "restart"
    assert variables["fixed_service_id"] == "demo-api"
    assert runner.calls[0][1] == "legacy-host"
    assert all(key not in variables for key in ("command", "argv", "extra_args"))


def test_missing_credential_reference_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPSPILOT_LEGACY_SSH_KEY_FILE", raising=False)
    configuration = load_deployment_configuration(CONFIG_PATH)
    factory = OperatorAnsibleRunnerFactory(
        configuration=configuration,
        configuration_path=CONFIG_PATH,
        playbook_root=PLAYBOOK_ROOT,
    )
    with pytest.raises(RuntimeError, match="credential reference"):
        factory.create(configuration.connections[0])


def test_same_semantic_restart_maps_to_systemd_unit_without_script() -> None:
    configuration = load_deployment_configuration(SYSTEMD_CONFIG_PATH)
    runner = RecordingRunner()
    executor = DeploymentAnsibleActionExecutor(
        configuration=configuration,
        resolver=ConfigDeploymentEnvironmentResolver(configuration),
        playbook_root=PLAYBOOK_ROOT,
        runner_factory=RecordingFactory(runner),  # type: ignore[arg-type]
    )

    asyncio.run(executor.execute(action()))

    variables = runner.calls[0][2]
    assert variables["control_type"] == "SYSTEMD"
    assert variables["fixed_systemd_unit"] == "opspilot-demo-api.service"
    assert variables["fixed_systemd_state"] == "restarted"
    assert variables["fixed_script_path"] == "/bin/false"


def test_stop_uses_operator_owned_stopped_verification_criteria() -> None:
    configuration = load_deployment_configuration(CONFIG_PATH)
    runner = RecordingRunner()
    executor = DeploymentAnsibleActionExecutor(
        configuration=configuration,
        resolver=ConfigDeploymentEnvironmentResolver(configuration),
        playbook_root=PLAYBOOK_ROOT,
        runner_factory=RecordingFactory(runner),  # type: ignore[arg-type]
    )

    stop = action(ActionType.STOP_SERVICE)
    asyncio.run(executor.execute(stop))
    asyncio.run(executor.verify(stop))

    assert runner.calls[0][2]["fixed_operation"] == "stop"
    verification = runner.calls[1][2]
    assert verification["verify_http"] == "false"
    assert verification["verify_process"] == "true"
    assert verification["fixed_expected_service_state"] == "stopped"


def test_playbooks_use_modules_and_bounded_argv_never_shell() -> None:
    service_playbook = (PLAYBOOK_ROOT / "deployment_service_control.yml").read_text()
    verification = (PLAYBOOK_ROOT / "deployment_verify.yml").read_text()

    assert "ansible.builtin.systemd_service" in service_playbook
    assert "ansible.builtin.command" in service_playbook
    assert "argv:" in service_playbook
    assert "ansible.builtin.shell" not in service_playbook + verification
    assert "extra_args" not in service_playbook + verification
