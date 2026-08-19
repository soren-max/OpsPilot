from __future__ import annotations

import hashlib
import os
import stat
import subprocess
import time
from pathlib import Path
from typing import Any, Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.command_profiles import CommandAction, CommandProfile, OutputParserConfig
from app.core.config import Settings
from app.core.enums import IntegrationConfigStatus
from app.db.base import utc_now
from app.executors.base import ExecutionResult
from app.executors.local_services import LocalServicesExecutor, LocalServicesExecutorConfig
from app.integration_schemas import (
    AllowlistInput,
    EnvironmentInput,
    ExecutionInput,
    IntegrationConfigInput,
    IntegrationConfigRead,
)
from app.models import (
    Environment,
    Host,
    OperationsIntegrationConfig,
    Service,
    ServiceDeployment,
)
from app.parsers.status_result import redact_sensitive_output
from app.services.redaction import redact_text


def credential_path(settings: Settings, reference: str) -> Path:
    root = Path(settings.credential_directory).resolve()
    candidate = (root / reference).resolve()
    if candidate.parent != root:
        raise ValueError("credential reference escapes the configured credential directory")
    return candidate


def credential_metadata(settings: Settings, reference: str) -> dict[str, Any]:
    path = credential_path(settings, reference)
    configured = path.is_file() and not path.is_symlink()
    fingerprint = None
    if configured:
        fingerprint = "SHA256:" + hashlib.sha256(path.read_bytes()).hexdigest()[:24]
    return {"name": reference, "configured": configured, "fingerprint": fingerprint}


def list_credentials(settings: Settings) -> list[dict[str, Any]]:
    root = Path(settings.credential_directory)
    if not root.is_dir():
        return []
    return [
        credential_metadata(settings, item.name)
        for item in sorted(root.iterdir(), key=lambda value: value.name)
        if item.is_file()
        and not item.is_symlink()
        and item.name not in {"known_hosts", "config", "authorized_keys"}
        and not item.name.endswith(".pub")
    ]


def store_credential(settings: Settings, name: str, private_key: str) -> dict[str, Any]:
    if not private_key.startswith("-----BEGIN ") or "PRIVATE KEY-----" not in private_key[:80]:
        raise ValueError("credential must be a PEM or OpenSSH private key")
    root = Path(settings.credential_directory)
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    if root.is_symlink():
        raise ValueError("credential directory must not be a symlink")
    if stat.S_IMODE(root.stat().st_mode) & 0o077:
        raise ValueError("credential directory permissions must be 0700")
    path = credential_path(settings, name)
    if path.exists():
        raise FileExistsError("credential reference already exists")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    descriptor = os.open(path, flags, 0o600)
    try:
        try:
            payload = private_key.encode("utf-8")
            written = 0
            while written < len(payload):
                count = os.write(descriptor, payload[written:])
                if count <= 0:
                    raise OSError("unable to write credential file")
                written += count
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
    except OSError:
        path.unlink(missing_ok=True)
        raise
    return credential_metadata(settings, name)


def read_config(db: Session, environment_id: str) -> OperationsIntegrationConfig | None:
    return db.scalar(
        select(OperationsIntegrationConfig).where(
            OperationsIntegrationConfig.environment_id == environment_id
        )
    )


def active_config(db: Session, environment_id: str) -> OperationsIntegrationConfig | None:
    config = read_config(db, environment_id)
    if (
        config is None
        or not config.enabled
        or config.status is not IntegrationConfigStatus.READY
        or not config.last_ssh_test_ok
        or not config.last_status_test_ok
        or config.validation_errors
    ):
        return None
    return config


def dynamic_allowlists(
    config: OperationsIntegrationConfig | None,
) -> dict[str, frozenset[str]]:
    if config is None:
        return {}
    return {
        "allowed_environments": frozenset(config.allowlist.get("environments", [])),
        "allowed_hosts": frozenset(config.allowlist.get("hosts", [])),
        "allowed_services": frozenset(config.allowlist.get("services", [])),
        "allowed_actions": frozenset(config.allowlist.get("actions", [])),
    }


def serialize_config(
    db: Session, config: OperationsIntegrationConfig, settings: Settings
) -> IntegrationConfigRead:
    environment = config.environment
    allowlisted_hosts = config.allowlist.get("hosts", [])
    allowlisted_services = config.allowlist.get("services", [])
    hosts = list(
        db.scalars(
            select(Host)
            .where(
                Host.environment_id == environment.id,
                Host.name.in_(allowlisted_hosts),
            )
            .order_by(Host.name)
        )
    )
    services = list(
        db.scalars(
            select(Service)
            .where(
                Service.environment_id == environment.id,
                Service.name.in_(allowlisted_services),
            )
            .order_by(Service.name)
        )
    )
    deployments = list(
        db.execute(
            select(Service.name, Host.name)
            .join(ServiceDeployment, ServiceDeployment.service_id == Service.id)
            .join(Host, Host.id == ServiceDeployment.host_id)
            .where(
                Service.environment_id == environment.id,
                Service.name.in_(allowlisted_services),
                Host.name.in_(allowlisted_hosts),
            )
        ).tuples()
    )
    host_by_service: dict[str, list[str]] = {}
    for service_name, host_name in deployments:
        host_by_service.setdefault(service_name, []).append(host_name)
    return IntegrationConfigRead(
        id=config.id,
        environment_id=environment.id,
        status=config.status,
        enabled=config.enabled,
        environment=EnvironmentInput(
            name=environment.name,
            code=environment.code,
            level=environment.environment_level,
        ),
        hosts=[
            {
                "id": host.id,
                "name": host.name,
                "address": host.address,
                "ssh_port": host.ssh_port,
                "ssh_username": host.ssh_username,
                "credential_reference": host.credential_reference,
                "credential": credential_metadata(
                    settings, host.credential_reference or "unconfigured"
                ),
            }
            for host in hosts
        ],
        services=[
            {
                "id": service.id,
                "name": service.name,
                "host_names": sorted(host_by_service.get(service.name, [])),
            }
            for service in services
        ],
        execution=ExecutionInput(
            services_sh_remote_path=config.remote_services_path,
            working_directory=config.remote_working_directory,
            timeout_seconds=config.timeout_seconds,
            status_argv=config.status_argv,
            start_argv=config.start_argv,
            stop_argv=config.stop_argv,
        ),
        parser=OutputParserConfig.model_validate(config.parser_config),
        allowlist=AllowlistInput.model_validate(config.allowlist),
        validation_errors=config.validation_errors,
        last_ssh_test_ok=config.last_ssh_test_ok,
        last_status_test_ok=config.last_status_test_ok,
        last_test_details=config.last_test_details,
    )


def save_config(
    db: Session,
    environment: Environment,
    body: IntegrationConfigInput,
) -> OperationsIntegrationConfig:
    environment.name = body.environment.name
    environment.code = body.environment.code
    environment.environment_level = body.environment.level
    environment.enabled = True
    existing_hosts = {
        item.name: item
        for item in db.scalars(select(Host).where(Host.environment_id == environment.id))
    }
    hosts: dict[str, Host] = {}
    for host_value in body.hosts:
        host = db.get(Host, host_value.id) if host_value.id else existing_hosts.get(host_value.name)
        if host is not None and host.environment_id != environment.id:
            raise ValueError("host id does not belong to the configured environment")
        if host is None:
            host = Host(environment=environment, name=host_value.name, mock_behavior="success")
        host.name = host_value.name
        host.address = host_value.address
        host.ssh_port = host_value.ssh_port
        host.ssh_username = host_value.ssh_username
        host.credential_reference = host_value.credential_reference
        host.enabled = True
        db.add(host)
        hosts[host_value.name] = host
    existing_services = {
        item.name: item
        for item in db.scalars(select(Service).where(Service.environment_id == environment.id))
    }
    services: dict[str, Service] = {}
    for service_value in body.services:
        service = (
            db.get(Service, service_value.id)
            if service_value.id
            else existing_services.get(service_value.name)
        )
        if service is not None and service.environment_id != environment.id:
            raise ValueError("service id does not belong to the configured environment")
        if service is None:
            service = Service(
                environment=environment,
                name=service_value.name,
                service_type="application",
                is_middleware=False,
            )
        service.name = service_value.name
        service.enabled = True
        db.add(service)
        services[service_value.name] = service
    db.flush()
    configured_service_ids = [service.id for service in services.values()]
    if configured_service_ids:
        for deployment in db.scalars(
            select(ServiceDeployment).where(
                ServiceDeployment.service_id.in_(configured_service_ids)
            )
        ):
            db.delete(deployment)
        db.flush()
    for service_value in body.services:
        for host_name in service_value.host_names:
            db.add(ServiceDeployment(service=services[service_value.name], host=hosts[host_name]))
    config = read_config(db, environment.id)
    if config is None:
        config = OperationsIntegrationConfig(
            environment=environment,
            remote_services_path=body.execution.services_sh_remote_path,
            remote_working_directory=body.execution.working_directory,
        )
        db.add(config)
    config.remote_services_path = body.execution.services_sh_remote_path
    config.remote_working_directory = body.execution.working_directory
    config.timeout_seconds = body.execution.timeout_seconds
    config.status_argv = body.execution.status_argv
    config.start_argv = body.execution.start_argv
    config.stop_argv = body.execution.stop_argv
    config.parser_config = body.parser.model_dump(mode="json")
    config.allowlist = body.allowlist.model_dump(mode="json")
    config.status = IntegrationConfigStatus.DRAFT
    config.enabled = False
    config.validation_errors = []
    config.last_ssh_test_ok = False
    config.last_status_test_ok = False
    config.last_test_details = {}
    config.validated_at = None
    db.flush()
    return config


def validate_config(
    db: Session, config: OperationsIntegrationConfig, settings: Settings
) -> list[str]:
    value = serialize_config(db, config, settings)
    errors: list[str] = []
    if not settings.services_script_path:
        errors.append("bootstrap services.script_path (local SSH wrapper) is not configured")
    else:
        wrapper = Path(settings.services_script_path)
        if (
            not wrapper.is_absolute()
            or not wrapper.is_file()
            or wrapper.is_symlink()
            or not os.access(wrapper, os.X_OK)
        ):
            errors.append("bootstrap services.script_path must be an executable absolute wrapper")
    if (
        not settings.services_working_directory
        or not Path(settings.services_working_directory).is_dir()
    ):
        errors.append("bootstrap services.working_directory is not confirmed")
    for host in value.hosts:
        reference = str(host["credential_reference"])
        path = credential_path(settings, reference)
        if not path.is_file() or path.is_symlink():
            errors.append(f"host {host['name']}: credential reference is not configured")
        elif stat.S_IMODE(path.stat().st_mode) & 0o077:
            errors.append(f"host {host['name']}: credential file permissions must be 0600")
    known_hosts = Path(
        settings.ssh_known_hosts_path or Path(settings.credential_directory) / "known_hosts"
    )
    if not known_hosts.is_file() or known_hosts.is_symlink():
        errors.append("strict known_hosts file is not configured")
    actions = set(config.allowlist.get("actions", []))
    writes = actions.intersection({"start", "stop"})
    if (
        settings.environment_mode not in {"integration-test", "production"}
        or settings.dry_run_only
        or not settings.execution_is_acknowledged
        or (bool(writes) and not settings.write_operations_enabled)
        or (
            config.environment.environment_level.value == "PRODUCTION"
            and bool(writes)
            and not settings.production_operations_enabled
        )
    ):
        errors.append(
            "execution security requires integration-test/production, dry_run_only=false, "
            "execution_acknowledged=true, write_operations_enabled=true for writes, and "
            "production_operations_enabled=true for production writes"
        )
    parser = OutputParserConfig.model_validate(config.parser_config)
    if parser.type == "raw" and writes:
        errors.append("raw parser cannot verify start/stop operations")
    for action in writes:
        if not getattr(config, f"{action}_argv", None):
            errors.append(f"enabled action {action} requires an explicit command profile argv")
    config.validation_errors = errors
    config.enabled = False
    config.status = (
        IntegrationConfigStatus.VALIDATED if not errors else IntegrationConfigStatus.DRAFT
    )
    config.validated_at = utc_now() if not errors else None
    return errors


def _process_environment(
    config: OperationsIntegrationConfig, host: Host, settings: Settings
) -> dict[str, str]:
    known_hosts = settings.ssh_known_hosts_path or str(
        Path(settings.credential_directory) / "known_hosts"
    )
    return {
        "OPSPILOT_SSH_HOST": host.address or "",
        "OPSPILOT_SSH_PORT": str(host.ssh_port or 22),
        "OPSPILOT_SSH_USER": host.ssh_username or "",
        "OPSPILOT_SSH_PRIVATE_KEY_PATH": str(
            credential_path(settings, host.credential_reference or "unconfigured")
        ),
        "OPSPILOT_SSH_KNOWN_HOSTS_PATH": known_hosts,
        "OPSPILOT_REMOTE_SERVICES_SCRIPT": config.remote_services_path,
        "OPSPILOT_REMOTE_WORKING_DIRECTORY": config.remote_working_directory,
        "OPSPILOT_SSH_CONNECT_TIMEOUT_SECONDS": str(min(config.timeout_seconds, 30)),
    }


def configured_host_ids(db: Session, config: OperationsIntegrationConfig) -> set[str]:
    return set(
        db.scalars(
            select(Host.id).where(
                Host.environment_id == config.environment_id,
                Host.enabled.is_(True),
                Host.name.in_(config.allowlist.get("hosts", [])),
            )
        )
    )


def configured_deployment_keys(db: Session, config: OperationsIntegrationConfig) -> set[str]:
    return {
        f"{host_id}:{service_id}"
        for host_id, service_id in db.execute(
            select(ServiceDeployment.host_id, ServiceDeployment.service_id)
            .join(Host, Host.id == ServiceDeployment.host_id)
            .join(Service, Service.id == ServiceDeployment.service_id)
            .where(
                Host.environment_id == config.environment_id,
                Service.environment_id == config.environment_id,
                Host.name.in_(config.allowlist.get("hosts", [])),
                Service.name.in_(config.allowlist.get("services", [])),
                Host.enabled.is_(True),
                Service.enabled.is_(True),
                ServiceDeployment.enabled.is_(True),
            )
        ).tuples()
    }


def all_configured_tests_passed(
    db: Session, config: OperationsIntegrationConfig
) -> tuple[bool, bool]:
    details = config.last_test_details if isinstance(config.last_test_details, dict) else {}
    ssh_results = details.get("ssh", {})
    status_results = details.get("status", {})
    ssh_ok = (
        isinstance(ssh_results, dict)
        and bool(configured_host_ids(db, config))
        and all(
            isinstance(ssh_results.get(host_id), dict)
            and ssh_results[host_id].get("success") is True
            for host_id in configured_host_ids(db, config)
        )
    )
    status_ok = (
        isinstance(status_results, dict)
        and bool(configured_deployment_keys(db, config))
        and all(
            isinstance(status_results.get(key), dict) and status_results[key].get("success") is True
            for key in configured_deployment_keys(db, config)
        )
    )
    return ssh_ok, status_ok


def build_config_executor(
    config: OperationsIntegrationConfig,
    host: Host,
    settings: Settings,
) -> LocalServicesExecutor:
    profile_name = f"db-operations-{config.id}"
    parser_name = f"db-parser-{config.id}"
    actions = list(config.allowlist.get("actions", []))
    command_actions: dict[Literal["status", "start", "stop"], CommandAction] = {
        "status": CommandAction(argv=config.status_argv)
    }
    if "start" in actions:
        command_actions["start"] = CommandAction(argv=config.start_argv)
    if "stop" in actions:
        command_actions["stop"] = CommandAction(argv=config.stop_argv)
    profile = CommandProfile(
        capabilities=actions,
        parser=parser_name,
        actions=command_actions,
    )
    parser = OutputParserConfig.model_validate(config.parser_config)
    allowlist = config.allowlist
    return LocalServicesExecutor(
        LocalServicesExecutorConfig(
            script_path=settings.services_script_path,
            working_directory=settings.services_working_directory,
            command_profile=profile_name,
            output_parser=parser_name,
            timeout_seconds=config.timeout_seconds,
            allowed_environments=frozenset(allowlist.get("environments", [])),
            allowed_hosts=frozenset(allowlist.get("hosts", [])),
            allowed_services=frozenset(allowlist.get("services", [])),
            allowed_actions=frozenset(actions),
            command_profiles={profile_name: profile},
            output_parsers={parser_name: parser},
            process_environment=_process_environment(config, host, settings),
            max_output_bytes=settings.max_output_bytes,
            termination_grace_seconds=settings.termination_grace_seconds,
        )
    )


def test_ssh(config: OperationsIntegrationConfig, host: Host, settings: Settings) -> dict[str, Any]:
    environment = _process_environment(config, host, settings)
    command = [
        "ssh",
        "-o",
        "BatchMode=yes",
        "-o",
        "StrictHostKeyChecking=yes",
        "-o",
        f"UserKnownHostsFile={environment['OPSPILOT_SSH_KNOWN_HOSTS_PATH']}",
        "-o",
        f"ConnectTimeout={min(config.timeout_seconds, 30)}",
        "-i",
        environment["OPSPILOT_SSH_PRIVATE_KEY_PATH"],
        "-p",
        environment["OPSPILOT_SSH_PORT"],
        "--",
        f"{environment['OPSPILOT_SSH_USER']}@{environment['OPSPILOT_SSH_HOST']}",
        "hostname",
    ]
    started = time.monotonic()
    try:
        completed = subprocess.run(
            command,
            shell=False,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            timeout=min(config.timeout_seconds, 30),
            check=False,
            env={"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8"},
        )
        error = (
            redact_text(
                redact_sensitive_output(completed.stderr),
                hostnames=(host.address or "", host.name),
                accounts=(host.ssh_username or "",),
            )
            or ""
        )[:2048]
        success = completed.returncode == 0
        exit_code = completed.returncode
    except (OSError, subprocess.TimeoutExpired) as exc:
        success = False
        error = (
            redact_text(
                redact_sensitive_output(str(exc)),
                hostnames=(host.address or "", host.name),
                accounts=(host.ssh_username or "",),
            )
            or ""
        )[:2048]
        exit_code = 124 if isinstance(exc, subprocess.TimeoutExpired) else 127
    fingerprint = _known_host_fingerprint(
        Path(environment["OPSPILOT_SSH_KNOWN_HOSTS_PATH"]),
        host.address or "",
        host.ssh_port or 22,
    )
    return {
        "success": success,
        "latency_ms": int((time.monotonic() - started) * 1000),
        "error": error or None,
        "exit_code": exit_code,
        "host_fingerprint": fingerprint,
        "host_key_status": "verified"
        if success and fingerprint
        else "known"
        if fingerprint
        else "missing",
        "credential_fingerprint": credential_metadata(
            settings, host.credential_reference or "unconfigured"
        )["fingerprint"],
    }


def _known_host_fingerprint(known_hosts: Path, address: str, port: int) -> str | None:
    if not known_hosts.is_file() or known_hosts.is_symlink() or not address:
        return None
    lookup = address if port == 22 else f"[{address}]:{port}"
    try:
        found = subprocess.run(
            ["ssh-keygen", "-F", lookup, "-f", str(known_hosts)],
            shell=False,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
            env={"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8"},
        )
        key_line = next(
            (line for line in found.stdout.splitlines() if line and not line.startswith("#")),
            None,
        )
        if key_line is None:
            return None
        fingerprint = subprocess.run(
            ["ssh-keygen", "-lf", "-"],
            shell=False,
            input=key_line,
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
            env={"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8"},
        )
        fields = fingerprint.stdout.split()
        return fields[1] if fingerprint.returncode == 0 and len(fields) > 1 else None
    except (OSError, subprocess.TimeoutExpired):
        return None


def test_status(
    config: OperationsIntegrationConfig,
    environment: Environment,
    host: Host,
    service: Service,
    settings: Settings,
) -> tuple[dict[str, Any], ExecutionResult]:
    from app.services.worker import ConfigurationTestWorker

    result = ConfigurationTestWorker(settings).run_status(config, environment, host, service)
    details = {
        "success": result.success,
        "result": "SUCCESS" if result.success else "FAILED",
        "command_profile": {"action": "status", "argv": config.status_argv},
        "duration_ms": result.duration_ms,
        "exit_code": result.exit_code,
        "parsed_state": result.service_state,
        "stdout": (
            redact_text(
                redact_sensitive_output(result.output or ""),
                hostnames=(host.address or "", host.name),
                accounts=(host.ssh_username or "",),
            )
            or ""
        )[:8192],
        "stderr": (
            redact_text(
                redact_sensitive_output(result.error_message or ""),
                hostnames=(host.address or "", host.name),
                accounts=(host.ssh_username or "",),
            )
            or ""
        )[:8192],
    }
    return details, result
