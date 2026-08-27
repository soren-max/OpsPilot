import json
from pathlib import Path

import pytest
import yaml  # type: ignore[import-untyped]
from pydantic import ValidationError

from app.deployment.config import load_deployment_configuration
from app.deployment.models import DeploymentConfiguration, ServiceControlType
from app.deployment.resolver import ConfigDeploymentEnvironmentResolver
from app.domain.actions.models import TargetEnvironment

ROOT = Path(__file__).parents[3]
LEGACY = ROOT / "deployment/examples/legacy-test.yaml"
SYSTEMD = ROOT / "deployment/examples/systemd-test.yaml"


def payload(path: Path = LEGACY) -> dict[str, object]:
    value = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def validate(value: dict[str, object]) -> DeploymentConfiguration:
    return DeploymentConfiguration.model_validate_json(json.dumps(value))


def test_synthetic_examples_are_strict_and_support_both_control_modes() -> None:
    legacy = load_deployment_configuration(LEGACY)
    systemd = load_deployment_configuration(SYSTEMD)

    assert legacy.service_controls[0].control_type is ServiceControlType.FIXED_SCRIPT
    assert systemd.service_controls[0].control_type is ServiceControlType.SYSTEMD
    assert legacy.targets[0].service == systemd.targets[0].service == "demo-api"
    assert legacy.connections[0].credential_env_ref == "OPSPILOT_LEGACY_SSH_KEY_FILE"


def test_resolver_maps_only_exact_semantic_identity() -> None:
    configuration = load_deployment_configuration(LEGACY)
    resolver = ConfigDeploymentEnvironmentResolver(configuration)

    resolved = resolver.resolve(
        service="demo-api",
        environment=TargetEnvironment.TEST,
        target_ref="demo-api",
    )
    assert resolved.profile_id == "example-legacy-test"
    with pytest.raises(ValueError, match="No unique approved"):
        resolver.resolve(
            service="demo-api",
            environment=TargetEnvironment.PRODUCTION,
            target_ref="demo-api",
        )
    with pytest.raises(ValueError, match="No unique approved"):
        resolver.resolve(
            service="unknown-service",
            environment=TargetEnvironment.TEST,
            target_ref="demo-api",
        )


@pytest.mark.parametrize(
    "mutation",
    [
        lambda value: value.update({"unknown_field": True}),
        lambda value: value["targets"][0].update({"environment": "qa"}),  # type: ignore[index,union-attr]
        lambda value: value["targets"][0].update({"allowed_actions": ["run_command"]}),  # type: ignore[index,union-attr]
        lambda value: value["inventory_catalog"].update({"legacy-lab": "../secret.ini"}),  # type: ignore[union-attr]
        lambda value: value["targets"].append(dict(value["targets"][0])),  # type: ignore[index,union-attr]
    ],
)
def test_invalid_configuration_fails_closed(mutation: object) -> None:
    value = payload()
    mutation(value)  # type: ignore[operator]
    with pytest.raises(ValidationError):
        validate(value)


@pytest.mark.parametrize("injection", ["; rm -rf", "$(id)", "| bash", "--exec"])
def test_command_injection_cannot_enter_service_mapping(injection: str) -> None:
    value = payload()
    controls = value["service_controls"]
    assert isinstance(controls, list)
    controls[0]["service_mapping"]["demo-api"] = injection
    with pytest.raises(ValidationError, match="unsafe"):
        validate(value)


def test_duplicate_service_yaml_key_is_rejected(tmp_path: Path) -> None:
    raw = LEGACY.read_text(encoding="utf-8").replace(
        "      demo-worker: demo-worker",
        "      demo-api: duplicate-demo-api\n      demo-worker: demo-worker",
    )
    duplicate = tmp_path / "duplicate-service.yaml"
    duplicate.write_text(raw, encoding="utf-8")

    with pytest.raises(ValueError, match="Duplicate YAML key"):
        load_deployment_configuration(duplicate)
