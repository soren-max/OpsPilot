from pathlib import Path

import pytest

from app.core.command_profiles import CommandAction
from app.core.enums import OperationAction
from app.executors.base import ExecutionRequest
from app.executors.command_builders.services_command import (
    CommandProfileNotConfigured,
    ServicesCommandBuilder,
)

SCRIPT = Path(__file__).parent / "fixtures" / "fake_services.sh"


def request(
    *,
    host: str = "test-host",
    service: str = "running",
    parameters: dict[str, object] | None = None,
) -> ExecutionRequest:
    return ExecutionRequest(
        action=OperationAction.STATUS,
        environment_code="devtest",
        host_name=host,
        service_name=service,
        parameters=parameters or {},
    )


def test_fixture_profile_builds_an_argv_array_only() -> None:
    argv = ServicesCommandBuilder(str(SCRIPT), "test-fixture-v1").build(request())
    assert argv == [str(SCRIPT), "status", "devtest", "test-host", "running"]


def test_pending_profile_has_no_guessed_command() -> None:
    with pytest.raises(CommandProfileNotConfigured, match="pending confirmation"):
        ServicesCommandBuilder(str(SCRIPT), "pending-confirmation").build(request())


@pytest.mark.parametrize(
    ("action", "method_name"),
    [
        (OperationAction.START, "build_start_command"),
        (OperationAction.STOP, "build_stop_command"),
    ],
)
def test_write_command_extension_points_are_pending(
    action: OperationAction, method_name: str
) -> None:
    builder = ServicesCommandBuilder(str(SCRIPT), "test-fixture-v1")
    pending_request = ExecutionRequest(
        action=action,
        environment_code="devtest",
        host_name="test-host",
        service_name="running",
    )
    with pytest.raises(CommandProfileNotConfigured, match="pending confirmation"):
        getattr(builder, method_name)(pending_request)
    with pytest.raises(CommandProfileNotConfigured, match="pending confirmation"):
        builder.build(pending_request)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("host", "host;id"),
        ("host", "host|id"),
        ("host", "host>file"),
        ("service", "service`id`"),
        ("service", "service\nid"),
    ],
)
def test_builder_rejects_command_injection_characters(field: str, value: str) -> None:
    values = {"host": "test-host", "service": "running"}
    values[field] = value
    with pytest.raises(ValueError, match="unsupported characters"):
        ServicesCommandBuilder(str(SCRIPT), "test-fixture-v1").build(request(**values))


@pytest.mark.parametrize("key", ["command", "script_path", "playbook", "extra-vars"])
def test_builder_rejects_command_shaping_parameters(key: str) -> None:
    with pytest.raises(ValueError, match="forbidden command fields"):
        ServicesCommandBuilder(str(SCRIPT), "test-fixture-v1").build(
            request(parameters={key: "forbidden"})
        )


@pytest.mark.parametrize("argv", [["ansible-playbook"], ["status.yml"], ["/usr/bin/ansible"]])
def test_command_action_rejects_direct_ansible_and_playbooks(argv: list[str]) -> None:
    with pytest.raises(ValueError, match=r"services\.sh contract"):
        CommandAction(argv=argv)
