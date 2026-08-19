from __future__ import annotations

import os
import stat
from pathlib import Path
from typing import Any, Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.models import (
    Environment,
    Host,
    OperationsIntegrationConfig,
    Service,
    ServiceDeployment,
)
from app.parsers.configurable import build_status_parser
from app.services.integration_config import (
    all_configured_tests_passed,
    configured_deployment_keys,
    credential_path,
)

BUILTIN_OUTPUT_PARSERS = {"json_status", "legacy_text_status", "raw_output"}
REQUIRED_ACTIONS: tuple[Literal["status"], Literal["start"], Literal["stop"]] = (
    "status",
    "start",
    "stop",
)


def dynamic_configuration_readiness(db: Session, settings: Settings) -> dict[str, Any] | None:
    """Return no overlay for legacy YAML-only deployments, preserving compatibility."""
    configs = list(db.scalars(select(OperationsIntegrationConfig)))
    if not configs:
        return None
    checks: dict[str, dict[str, str]] = {}
    for index, config in enumerate(configs, start=1):
        prefix = f"config_{index}"
        hosts = list(
            db.scalars(
                select(Host).where(
                    Host.environment_id == config.environment_id,
                    Host.name.in_(config.allowlist.get("hosts", [])),
                )
            )
        )
        services = list(
            db.scalars(
                select(Service).where(
                    Service.environment_id == config.environment_id,
                    Service.name.in_(config.allowlist.get("services", [])),
                )
            )
        )
        allowlist = config.allowlist
        expected_host_names = set(config.allowlist.get("hosts", []))
        expected_service_names = set(config.allowlist.get("services", []))
        complete = (
            {host.name for host in hosts} == expected_host_names
            and {service.name for service in services} == expected_service_names
            and bool(configured_deployment_keys(db, config))
            and all(
                host.enabled
                and host.address
                and host.ssh_port
                and host.ssh_username
                and host.credential_reference
                for host in hosts
            )
            and all(service.enabled for service in services)
        )
        checks[f"{prefix}_catalog"] = _result(
            complete,
            "environment, hosts, services and SSH target metadata are complete",
            "environment/host/service or SSH target metadata is incomplete",
        )
        credentials_ok = bool(hosts)
        for host in hosts:
            path = credential_path(settings, host.credential_reference or "unconfigured")
            try:
                credential_safe = bool(
                    path.is_file()
                    and not path.is_symlink()
                    and not (stat.S_IMODE(path.stat().st_mode) & 0o077)
                )
            except OSError:
                credential_safe = False
            credentials_ok = credentials_ok and credential_safe
        known_hosts = Path(
            settings.ssh_known_hosts_path or Path(settings.credential_directory) / "known_hosts"
        )
        credentials_ok = credentials_ok and known_hosts.is_file() and not known_hosts.is_symlink()
        checks[f"{prefix}_credentials"] = _result(
            credentials_ok,
            "credential references and strict known_hosts are available with safe permissions",
            "credential reference or strict known_hosts is missing or unsafe",
        )
        paths_ok = bool(
            config.remote_services_path.startswith("/")
            and config.remote_working_directory.startswith("/")
        )
        checks[f"{prefix}_execution_paths"] = _result(
            paths_ok,
            "remote services.sh path and working directory are confirmed",
            "remote services.sh path or working directory is not confirmed",
        )
        actions = set(allowlist.get("actions", []))
        writes = actions.intersection({"start", "stop"})
        profile_ok = bool(
            config.status_argv
            and config.parser_config
            and all(getattr(config, f"{action}_argv", None) for action in writes)
        )
        checks[f"{prefix}_profile_parser"] = _result(
            profile_ok,
            "all enabled command profiles and the verification parser are configured",
            "an enabled command profile or verification parser is missing",
        )
        allowlist_ok = bool(
            allowlist.get("environments")
            and allowlist.get("hosts")
            and allowlist.get("services")
            and actions
            and "status" in actions
            and actions <= set(REQUIRED_ACTIONS)
        )
        checks[f"{prefix}_allowlist"] = _result(
            allowlist_ok,
            "non-empty allowlists permit only explicit status/start/stop actions",
            "allowlists must be non-empty, include status, and contain only status/start/stop",
        )
        parser_type = config.parser_config.get("type")
        security_ok = (
            settings.execution_is_acknowledged
            and not settings.dry_run_only
            and (not writes or settings.write_operations_enabled)
            and (
                config.environment.environment_level.value != "PRODUCTION"
                or not writes
                or settings.production_operations_enabled
            )
            and not (writes and parser_type == "raw")
        )
        checks[f"{prefix}_security"] = _result(
            security_ok,
            "dynamic configuration cannot bypass execution security switches",
            "dynamic configuration conflicts with execution security requirements",
        )
        ssh_tests_ok, status_tests_ok = all_configured_tests_passed(db, config)
        ready = (
            config.status.value == "READY"
            and config.enabled
            and config.last_ssh_test_ok
            and config.last_status_test_ok
            and ssh_tests_ok
            and status_tests_ok
            and not config.validation_errors
        )
        checks[f"{prefix}_state"] = _result(
            ready,
            "configuration is READY, tested and enabled",
            f"configuration state is {config.status.value}; "
            "successful tests and enablement required",
        )
    return {
        "status": "ready"
        if checks and all(item["status"] == "ok" for item in checks.values())
        else "not_ready",
        "checks": checks,
    }


def _result(ok: bool, success: str, failure: str) -> dict[str, str]:
    return {"status": "ok" if ok else "failed", "reason": success if ok else failure}


def _catalog_checks(db: Session, settings: Settings) -> dict[str, dict[str, str]]:
    allowed_environments = settings.allowed_environment_set
    environment_ok = (
        bool(allowed_environments)
        and settings.environment in allowed_environments
        and not any("<" in value or "${" in value for value in allowed_environments)
    )
    checks = {
        "allowlist_environment": _result(
            environment_ok,
            f"environment {settings.environment!r} is explicitly allowlisted",
            f"environment {settings.environment!r} is not in a concrete environment allowlist",
        )
    }

    environment = db.scalar(
        select(Environment).where(
            Environment.code == settings.environment,
            Environment.enabled.is_(True),
        )
    )
    checks["catalog_environment"] = _result(
        environment is not None,
        f"enabled catalog environment {settings.environment!r} exists",
        f"enabled catalog environment {settings.environment!r} is missing; "
        "run app.seed after review",
    )

    allowed_hosts = settings.allowed_host_set
    allowed_services = settings.allowed_service_set
    host_names: set[str] = set()
    service_names: set[str] = set()
    deployment_pairs: set[tuple[str, str]] = set()
    if environment is not None:
        host_names = set(
            db.scalars(
                select(Host.name).where(
                    Host.environment_id == environment.id,
                    Host.enabled.is_(True),
                    Host.name.in_(allowed_hosts),
                )
            )
        )
        service_names = set(
            db.scalars(
                select(Service.name).where(
                    Service.environment_id == environment.id,
                    Service.enabled.is_(True),
                    Service.name.in_(allowed_services),
                )
            )
        )
        deployment_pairs = set(
            db.execute(
                select(Service.name, Host.name)
                .join(ServiceDeployment, ServiceDeployment.service_id == Service.id)
                .join(Host, Host.id == ServiceDeployment.host_id)
                .where(
                    Service.environment_id == environment.id,
                    Host.environment_id == environment.id,
                    ServiceDeployment.enabled.is_(True),
                    Service.name.in_(allowed_services),
                    Host.name.in_(allowed_hosts),
                )
            ).tuples()
        )
    missing_hosts = sorted(allowed_hosts - host_names)
    missing_services = sorted(allowed_services - service_names)
    checks["allowlist_hosts"] = _result(
        bool(allowed_hosts) and not missing_hosts,
        "every allowlisted host exists and is enabled in the current environment",
        "allowlisted hosts are empty or absent from the current environment: "
        + (", ".join(missing_hosts) or "<empty>"),
    )
    checks["allowlist_services"] = _result(
        bool(allowed_services) and not missing_services,
        "every allowlisted service exists and is enabled in the current environment",
        "allowlisted services are empty or absent from the current environment: "
        + (", ".join(missing_services) or "<empty>"),
    )
    deployed_hosts = {host for _, host in deployment_pairs}
    deployed_services = {service for service, _ in deployment_pairs}
    deployment_ok = (
        bool(deployment_pairs)
        and allowed_hosts <= deployed_hosts
        and allowed_services <= deployed_services
    )
    checks["catalog_deployments"] = _result(
        deployment_ok,
        "all allowlisted hosts and services participate in enabled deployments",
        "real allowlist catalog deployments are incomplete",
    )
    return checks


def local_services_readiness(db: Session, settings: Settings) -> dict[str, Any]:
    """Perform read-only static preflight checks; never invoke the configured script."""
    checks: dict[str, dict[str, str]] = {}
    checks["executor"] = _result(
        settings.selected_executor == "local_services",
        "executor.type is local_services",
        f"executor.type must be local_services, got {settings.selected_executor!r}",
    )

    script = Path(settings.services_script_path) if settings.services_script_path else None
    script_absolute = bool(script and script.is_absolute())
    checks["script_absolute"] = _result(
        script_absolute,
        "services.script_path is absolute",
        "services.script_path must be a configured absolute path",
    )
    script_exists = bool(script_absolute and script and script.is_file())
    checks["script_exists"] = _result(
        script_exists,
        "services script exists and is a regular file",
        "services script does not exist or is not a regular file",
    )
    script_symlink = bool(script and script.is_symlink())
    checks["script_not_symlink"] = _result(
        script_exists and not script_symlink,
        "services script is not a symlink",
        "services script must exist and symlinks are forbidden",
    )
    script_executable = bool(script_exists and script and os.access(script, os.X_OK))
    checks["script_executable"] = _result(
        script_executable,
        "services script is executable by the runtime user",
        "services script is not executable by the runtime user",
    )

    working = (
        Path(settings.services_working_directory) if settings.services_working_directory else None
    )
    working_absolute = bool(working and working.is_absolute())
    checks["working_directory_absolute"] = _result(
        working_absolute,
        "services.working_directory is absolute",
        "services.working_directory must be a configured absolute path",
    )
    working_exists = bool(working_absolute and working and working.is_dir())
    checks["working_directory_exists"] = _result(
        working_exists,
        "services working directory exists",
        "services working directory does not exist or is not a directory",
    )
    working_enterable = bool(working_exists and working and os.access(working, os.X_OK))
    checks["working_directory_enterable"] = _result(
        working_enterable,
        "services working directory is enterable by the runtime user",
        "services working directory is not enterable by the runtime user",
    )
    working_not_symlink = bool(working_exists and working and not working.is_symlink())
    checks["working_directory_not_symlink"] = _result(
        working_not_symlink,
        "services working directory is not a symlink",
        "services working directory must exist and symlinks are forbidden",
    )

    profile = settings.command_profiles.get(settings.services_command_profile)
    checks["command_profile"] = _result(
        profile is not None,
        f"command profile {settings.services_command_profile!r} exists",
        f"command profile {settings.services_command_profile!r} does not exist",
    )
    required_profile_actions = tuple(
        action for action in REQUIRED_ACTIONS if action in settings.allowed_action_set
    )
    for action in required_profile_actions:
        action_config = profile.actions.get(action) if profile else None
        complete = bool(
            profile and action in profile.capabilities and action_config and action_config.argv
        )
        checks[f"profile_action_{action}"] = _result(
            complete,
            f"{action} capability has a non-empty argv array",
            "command profile must declare allowlisted "
            f"{action} capability and actions.{action}.argv",
        )
        concrete = bool(
            action_config and all("<" not in arg and "${" not in arg for arg in action_config.argv)
        )
        checks[f"profile_action_{action}_confirmed"] = _result(
            concrete,
            f"{action} argv contains no unresolved site placeholders",
            f"actions.{action}.argv still contains an unconfirmed site placeholder",
        )

    parser_name = profile.parser if profile else settings.services_output_parser
    parser_exists = parser_name in BUILTIN_OUTPUT_PARSERS or parser_name in settings.output_parsers
    checks["output_parser"] = _result(
        parser_exists,
        f"output parser {parser_name!r} exists",
        f"output parser {parser_name!r} does not exist",
    )
    parser_config = settings.output_parsers.get(parser_name)
    parser_error = ""
    if parser_config is not None:
        try:
            build_status_parser(parser_config)
        except (ImportError, TypeError, ValueError) as exc:
            parser_error = str(exc)
    checks["output_parser_loadable"] = _result(
        parser_exists and not parser_error,
        "output parser can be constructed",
        "output parser cannot be constructed: " + (parser_error or "not configured"),
    )
    parser_dump = str(parser_config.model_dump()) if parser_config else parser_name
    parser_confirmed = "<" not in parser_dump and "${" not in parser_dump
    checks["output_parser_confirmed"] = _result(
        parser_confirmed,
        "output parser contains no unresolved site placeholders",
        "output parser contract still contains an unconfirmed site placeholder",
    )
    raw_parser = parser_name == "raw_output" or bool(parser_config and parser_config.type == "raw")
    raw_with_writes = raw_parser and bool(
        {"start", "stop"}.intersection(settings.allowed_action_set)
    )
    checks["output_parser_write_safety"] = _result(
        not raw_with_writes,
        "raw_output is not being used as a write-operation verification parser",
        "raw_output is diagnostic-only and cannot be used when start/stop is allowlisted",
    )

    checks.update(_catalog_checks(db, settings))
    actions = settings.allowed_action_set
    actions_ok = bool(actions) and actions <= set(REQUIRED_ACTIONS)
    checks["allowlist_actions"] = _result(
        actions_ok,
        "action allowlist is non-empty and contains only status/start/stop",
        "action allowlist must be non-empty and contain only status/start/stop",
    )
    status_allowed = "status" in actions
    checks["status_allowed"] = _result(
        status_allowed,
        "status is explicitly allowlisted",
        "status must be explicitly allowlisted for the status preflight phase",
    )
    security_ok = (
        settings.environment_mode == "integration-test"
        and not settings.production_operations_enabled
        and not settings.dry_run_only
        and settings.execution_is_acknowledged
        and (not {"start", "stop"}.intersection(actions) or settings.write_operations_enabled)
        and (bool({"start", "stop"}.intersection(actions)) or not settings.write_operations_enabled)
    )
    checks["execution_safety"] = _result(
        security_ok,
        "integration-test mode and safety switches match the action allowlist",
        "requires integration-test, production disabled, dry_run_only=false, "
        "execution_acknowledged=true, and write_enabled matching the action allowlist",
    )
    return {
        "status": "ready"
        if checks and all(item["status"] == "ok" for item in checks.values())
        else "not_ready",
        "checks": checks,
    }


def local_services_bootstrap_readiness(db: Session, settings: Settings) -> dict[str, Any]:
    """Check only immutable deployment concerns when runtime config is stored in the DB."""
    full = local_services_readiness(db, settings)
    required = {
        "executor",
        "script_absolute",
        "script_exists",
        "script_not_symlink",
        "script_executable",
        "working_directory_absolute",
        "working_directory_exists",
        "working_directory_enterable",
        "working_directory_not_symlink",
    }
    checks = {key: value for key, value in full["checks"].items() if key in required}
    security_ok = (
        settings.environment_mode in {"integration-test", "production"}
        and not settings.dry_run_only
        and settings.execution_is_acknowledged
        and (
            settings.environment_mode == "production" or not settings.production_operations_enabled
        )
    )
    checks["execution_safety"] = _result(
        security_ok,
        "bootstrap security switches are explicit and internally consistent",
        "dynamic bootstrap requires dry_run_only=false, execution_acknowledged=true, "
        "and production writes only in production mode",
    )
    return {
        "status": "ready"
        if checks and all(item["status"] == "ok" for item in checks.values())
        else "not_ready",
        "checks": checks,
    }
