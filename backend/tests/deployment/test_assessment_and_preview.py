import asyncio
from pathlib import Path

from app.adapters.ansible.runner import AnsibleRunResult
from app.deployment.assessment import assess_migration
from app.deployment.cli import migration_assess, preview
from app.deployment.config import load_deployment_configuration
from app.deployment.doctor import run_doctor
from app.deployment.models import ReadinessLevel
from app.domain.actions.models import ActionStatus, ActionType, VerificationResult

ROOT = Path(__file__).parents[3]
CONFIG = ROOT / "deployment/examples/legacy-test.yaml"


def test_migration_assessment_reports_minimal_remediation_path() -> None:
    report = assess_migration(
        load_deployment_configuration(CONFIG), "example-legacy-test"
    )

    assert ReadinessLevel.OBSERVE_READY in report.readiness_levels
    assert ReadinessLevel.REMEDIATION_READY in report.readiness_levels
    assert ReadinessLevel.FULL_INCIDENT_READY not in report.readiness_levels
    assert report.result == "MINIMAL REMEDIATION PATH READY"


def test_preview_and_assessment_never_print_transport_secrets(capsys: object) -> None:
    assert preview("example-legacy-test") == 0
    assert migration_assess("example-legacy-test") == 0
    output = capsys.readouterr().out  # type: ignore[attr-defined]

    assert "RESTART_SERVICE" in output
    assert "FIXED_SCRIPT" in output
    assert "Required" in output
    for forbidden in (
        "id_ed25519",
        "OPSPILOT_LEGACY_SSH_KEY_FILE",
        "opspilot-demo/services.sh",
        "legacy-host",
        "password",
        "Bearer",
    ):
        assert forbidden not in output


class HealthyRunner:
    async def run(self, **_kwargs: object) -> AnsibleRunResult:
        return AnsibleRunResult(0, "ok", "")


class HealthyFactory:
    def create(self, _connection: object) -> HealthyRunner:
        return HealthyRunner()


class HealthyExecutor:
    playbook_root = ROOT / "backend/app/deployment/playbooks"

    async def verify(self, action: object) -> VerificationResult:
        del action
        return VerificationResult(
            action_type=ActionType.RESTART_SERVICE,
            target="demo-api",
            status=ActionStatus.SUCCEEDED,
            verified=True,
            summary="Synthetic verification passed.",
        )


def test_deployment_doctor_is_read_only_and_reports_all_checks(
    monkeypatch: object,
) -> None:
    monkeypatch.setenv("OPSPILOT_LEGACY_SSH_KEY_FILE", "/synthetic/secret-file")  # type: ignore[attr-defined]
    monkeypatch.setattr("app.deployment.doctor._tcp_ready", lambda *_args: True)  # type: ignore[attr-defined]
    monkeypatch.setattr("app.deployment.doctor._database_ready", lambda *_args: True)  # type: ignore[attr-defined]
    checks = asyncio.run(
        run_doctor(
            configuration=load_deployment_configuration(CONFIG),
            configuration_path=CONFIG,
            profile_id="example-legacy-test",
            executor=HealthyExecutor(),  # type: ignore[arg-type]
            runner_factory=HealthyFactory(),  # type: ignore[arg-type]
        )
    )
    assert checks
    assert all(check.passed for check in checks)
