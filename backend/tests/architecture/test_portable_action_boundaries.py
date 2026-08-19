import ast
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.domain.actions.models import (
    ActionRequest,
    ActionType,
    ServiceActionParams,
    TargetEnvironment,
)

APP_ROOT = Path(__file__).parents[2] / "app"
PROTECTED_LAYERS = (APP_ROOT / "domain", APP_ROOT / "application")
FORBIDDEN_IMPORT_PARTS = frozenset(
    {
        "subprocess",
        "paramiko",
        "executors",
        "services_adapter",
        "ssh_script",
        "local_services",
        "factory",
        "integration_config",
    }
)
FORBIDDEN_ACTION_FIELDS = frozenset(
    {
        "ssh_user",
        "ssh_port",
        "private_key",
        "credential_reference",
        "inventory_path",
        "playbook_path",
        "shell",
        "command",
        "extra_vars",
    }
)


def python_sources(root: Path) -> list[Path]:
    return sorted(path for path in root.rglob("*.py") if "__pycache__" not in path.parts)


def imported_modules(source: Path) -> set[str]:
    tree = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
    return modules


@pytest.mark.parametrize("layer", PROTECTED_LAYERS, ids=lambda path: path.name)
def test_domain_and_application_do_not_import_legacy_execution(layer: Path) -> None:
    violations: list[str] = []
    for source in python_sources(layer):
        for module in imported_modules(source):
            parts = set(module.split("."))
            forbidden = sorted(parts & FORBIDDEN_IMPORT_PARTS)
            if forbidden:
                location = source.relative_to(APP_ROOT)
                violations.append(f"{location}: {module} ({', '.join(forbidden)})")

    assert not violations, "Portable boundary violations:\n" + "\n".join(violations)


def test_action_request_schema_contains_no_transport_or_arbitrary_execution_fields() -> None:
    schema = ActionRequest.model_json_schema()
    schema_fields = {
        property_name
        for definition in schema.get("$defs", {}).values()
        for property_name in definition.get("properties", {})
    }
    schema_fields.update(schema.get("properties", {}))

    assert not schema_fields & FORBIDDEN_ACTION_FIELDS


@pytest.mark.parametrize("field", sorted(FORBIDDEN_ACTION_FIELDS))
def test_action_request_rejects_transport_and_arbitrary_execution_input(field: str) -> None:
    payload = {
        "action_type": ActionType.RESTART_SERVICE,
        "target": "web-01",
        "environment": TargetEnvironment.TEST,
        "parameters": ServiceActionParams(service="nginx").model_dump(),
        "reason": "Recover the unavailable web service.",
        field: "untrusted-value",
    }

    with pytest.raises(ValidationError):
        ActionRequest.model_validate(payload)
