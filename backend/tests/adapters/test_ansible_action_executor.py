import asyncio
from collections.abc import Mapping
from pathlib import Path

import pytest

from app.adapters.ansible import (
    AnsibleActionExecutor,
    AnsibleRunResult,
    SubprocessAnsibleRunner,
)
from app.domain.actions.models import (
    ActionRequest,
    ActionType,
    ServiceActionParams,
    TargetEnvironment,
)


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


def action(action_type: ActionType = ActionType.RESTART_SERVICE) -> ActionRequest:
    return ActionRequest(
        action_type=action_type,
        target="web-01",
        environment=TargetEnvironment.TEST,
        parameters=ServiceActionParams(service="nginx"),
        reason="Evidence shows that the service is unavailable.",
    )


def test_ansible_uses_fixed_playbook_mapping_and_generated_variables(tmp_path: Path) -> None:
    for name in ("restart_service.yml", "service_status.yml"):
        (tmp_path / name).write_text("---\n", encoding="utf-8")
    runner = RecordingRunner()
    executor = AnsibleActionExecutor(
        runner=runner,
        playbook_root=tmp_path,
    )

    preview = asyncio.run(executor.preview(action()))
    result = asyncio.run(executor.execute(action()))
    verification = asyncio.run(executor.verify(action()))

    assert preview.operation == "restart_service.yml"
    assert result.status.value == "succeeded"
    assert verification.verified is True
    assert [call[0].name for call in runner.calls] == [
        "restart_service.yml",
        "service_status.yml",
    ]
    assert all(call[2] == {"service_name": "nginx"} for call in runner.calls)


def test_subprocess_runner_rejects_playbook_outside_owned_root(tmp_path: Path) -> None:
    inventory = tmp_path / "inventory.ini"
    inventory.write_text("web-01 ansible_connection=local\n", encoding="utf-8")
    playbooks = tmp_path / "playbooks"
    playbooks.mkdir()
    outside = tmp_path / "caller-selected.yml"
    outside.write_text("---\n", encoding="utf-8")
    runner = SubprocessAnsibleRunner(inventory=inventory, playbook_root=playbooks)

    with pytest.raises(ValueError, match="application-owned"):
        asyncio.run(
            runner.run(
                playbook=outside,
                target="web-01",
                variables={"service_name": "nginx"},
            )
        )
