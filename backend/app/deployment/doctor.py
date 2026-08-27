from __future__ import annotations

import os
import shutil
import socket
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import create_engine, text

from app.adapters.ansible.deployment import (
    DeploymentAnsibleActionExecutor,
    OperatorAnsibleRunnerFactory,
)
from app.deployment.config import resolve_operator_path
from app.deployment.models import DeploymentConfiguration
from app.domain.actions.models import ActionRequest, ActionType, ServiceActionParams


@dataclass(frozen=True)
class DoctorCheck:
    name: str
    passed: bool


def semantic_action(configuration: DeploymentConfiguration, profile_id: str) -> ActionRequest:
    target = next(
        (item for item in configuration.targets if item.profile_id == profile_id), None
    )
    if target is None:
        raise ValueError("Unknown deployment target profile")
    return ActionRequest(
        action_type=ActionType.RESTART_SERVICE,
        target=target.target_ref,
        environment=target.environment,
        parameters=ServiceActionParams(service=target.service),
        reason="Preview operator-owned deployment compatibility mapping.",
    )


def _inventory_endpoint(inventory: Path, host_alias: str) -> tuple[str, int] | None:
    for raw_line in inventory.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith(("#", "[")):
            continue
        parts = line.split()
        if parts[0] != host_alias:
            continue
        variables = dict(part.split("=", 1) for part in parts[1:] if "=" in part)
        return variables.get("ansible_host", host_alias), int(
            variables.get("ansible_port", "22")
        )
    return None


def _tcp_ready(host: str, port: int, timeout: float = 2.0) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def _database_ready(environment_ref: str | None) -> bool:
    if environment_ref is None:
        return True
    url = os.environ.get(environment_ref)
    if not url:
        return False
    try:
        engine = create_engine(url, pool_pre_ping=True)
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        engine.dispose()
        return True
    except Exception:
        return False


async def run_doctor(
    *,
    configuration: DeploymentConfiguration,
    configuration_path: Path,
    profile_id: str,
    executor: DeploymentAnsibleActionExecutor,
    runner_factory: OperatorAnsibleRunnerFactory,
) -> tuple[DoctorCheck, ...]:
    target = next(
        (item for item in configuration.targets if item.profile_id == profile_id), None
    )
    if target is None:
        return (DoctorCheck("target profile", False),)
    connection = next(
        item
        for item in configuration.connections
        if item.id == target.connection_profile_ref
    )
    inventory = resolve_operator_path(
        configuration_path, configuration.inventory_catalog[connection.inventory_ref]
    )
    credential_ready = not connection.credential_env_ref or bool(
        os.environ.get(connection.credential_env_ref)
    )
    endpoint = (
        _inventory_endpoint(inventory, connection.host_alias) if inventory.is_file() else None
    )
    ssh_ready = bool(endpoint and _tcp_ready(*endpoint))
    ansible_ready = False
    privilege_ready = False
    health_ready = False
    if inventory.is_file() and credential_ready:
        try:
            runner = runner_factory.create(connection)
            result = await runner.run(
                playbook=executor.playbook_root / "deployment_doctor.yml",
                target=connection.host_alias,
                variables={},
            )
            ansible_ready = result.exit_code == 0
            privilege_ready = ansible_ready
            verification = await executor.verify(semantic_action(configuration, profile_id))
            health_ready = verification.verified
        except Exception:
            ansible_ready = False
    ports_ready = bool(
        endpoint
        and all(_tcp_ready(endpoint[0], port) for port in configuration.required_ports)
    )
    control = next(
        item
        for item in configuration.service_controls
        if item.id == target.service_control_profile_ref
    )
    return (
        DoctorCheck("configuration schema", True),
        DoctorCheck("target profile", True),
        DoctorCheck("inventory exists", inventory.is_file()),
        DoctorCheck("credential reference", credential_ready),
        DoctorCheck("SSH reachability", ssh_ready),
        DoctorCheck("Ansible connectivity", ansible_ready),
        DoctorCheck("privilege capability", privilege_ready),
        DoctorCheck("service mapping", target.service in control.service_mapping),
        DoctorCheck("health endpoint", health_ready),
        DoctorCheck("database", _database_ready(configuration.database_url_env_ref)),
        DoctorCheck("required ports", ports_ready),
    )


def ansible_binary() -> Path:
    binary = shutil.which("ansible-playbook")
    if binary is None:
        raise RuntimeError("ansible-playbook is unavailable")
    return Path(binary)
