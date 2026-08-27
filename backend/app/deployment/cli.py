from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from app.adapters.ansible.deployment import (
    DeploymentAnsibleActionExecutor,
    OperatorAnsibleRunnerFactory,
)
from app.deployment.assessment import assess_migration
from app.deployment.config import load_deployment_configuration
from app.deployment.doctor import ansible_binary, run_doctor, semantic_action
from app.deployment.resolver import ConfigDeploymentEnvironmentResolver

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
EXAMPLE_ROOT = REPOSITORY_ROOT / "deployment" / "examples"
PLAYBOOK_ROOT = Path(__file__).resolve().parent / "playbooks"


def resolve_profile(value: str) -> tuple[Path, str]:
    direct = Path(value)
    candidates = [direct, EXAMPLE_ROOT / f"{value}.yaml"]
    for candidate in candidates:
        if candidate.is_file():
            configuration = load_deployment_configuration(candidate)
            if len(configuration.targets) != 1:
                raise ValueError("A path argument must contain exactly one target for CLI use")
            return candidate.resolve(), configuration.targets[0].profile_id
    for candidate in sorted(EXAMPLE_ROOT.glob("*.yaml")):
        configuration = load_deployment_configuration(candidate)
        if any(item.profile_id == value for item in configuration.targets):
            return candidate.resolve(), value
    raise ValueError("Unknown deployment profile")


def build_executor(
    config_path: Path,
    *,
    binary: Path = Path("/usr/bin/ansible-playbook"),
) -> tuple[DeploymentAnsibleActionExecutor, OperatorAnsibleRunnerFactory]:
    configuration = load_deployment_configuration(config_path)
    resolver = ConfigDeploymentEnvironmentResolver(configuration)
    factory = OperatorAnsibleRunnerFactory(
        configuration=configuration,
        configuration_path=config_path,
        playbook_root=PLAYBOOK_ROOT,
        binary=binary,
    )
    return (
        DeploymentAnsibleActionExecutor(
            configuration=configuration,
            resolver=resolver,
            playbook_root=PLAYBOOK_ROOT,
            runner_factory=factory,
        ),
        factory,
    )


def preview(profile_value: str) -> int:
    config_path, profile_id = resolve_profile(profile_value)
    configuration = load_deployment_configuration(config_path)
    executor, _ = build_executor(config_path)
    assessment = executor.deployment_preview(
        semantic_action(configuration, profile_id), approval_required=True
    )
    checks = ", ".join(item.value for item in assessment.verification)
    print("Deployment Preview")
    print(f"Semantic Action: {assessment.semantic_action.name}")
    print(f"Target: {assessment.service} / {assessment.environment}")
    print(f"Target Reference: {assessment.target_ref}")
    print(f"Execution Backend: {assessment.execution_backend}")
    print(f"Control Type: {assessment.control_type.value}")
    print(f"Verification: {checks}")
    print(f"Approval: {'Required' if assessment.approval_required else 'Not Required'}")
    return 0


def doctor(profile_value: str) -> int:
    config_path, profile_id = resolve_profile(profile_value)
    configuration = load_deployment_configuration(config_path)
    executor, factory = build_executor(config_path, binary=ansible_binary())
    checks = asyncio.run(
        run_doctor(
            configuration=configuration,
            configuration_path=config_path,
            profile_id=profile_id,
            executor=executor,
            runner_factory=factory,
        )
    )
    print("OpsPilot Deployment Doctor (read-only)")
    for check in checks:
        print(f"[{'PASS' if check.passed else 'FAIL'}] {check.name}")
    failures = sum(not item.passed for item in checks)
    print("\nPASS: environment is ready" if not failures else f"\nFAIL: {failures} check(s) failed")
    return 1 if failures else 0


def migration_assess(profile_value: str) -> int:
    config_path, profile_id = resolve_profile(profile_value)
    report = assess_migration(load_deployment_configuration(config_path), profile_id)
    print("Environment Compatibility Report")
    for item in report.items:
        print(f"{item.capability:<22} {item.status}")
    print("\nReadiness Levels:")
    for level in sorted(report.readiness_levels):
        print(level.value)
    print(f"\nResult:\n{report.result}")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Read-only deployment compatibility tooling")
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command in ("preview", "doctor", "assess"):
        child = subparsers.add_parser(command)
        child.add_argument("--profile", required=True)
    args = parser.parse_args()
    operation = {"preview": preview, "doctor": doctor, "assess": migration_assess}[
        args.command
    ]
    raise SystemExit(operation(args.profile))


if __name__ == "__main__":
    main()
