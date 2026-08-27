import ast
from pathlib import Path

from app.adapters.mcp.contracts import RemediationToolInput
from app.domain.actions.models import ActionRequest
from app.workflows.incident.investigator import InvestigationResult

APP_ROOT = Path(__file__).parents[2] / "app"
PROTECTED = (
    APP_ROOT / "domain",
    APP_ROOT / "application",
    APP_ROOT / "workflows",
    APP_ROOT / "ai",
    APP_ROOT / "adapters/mcp",
)
FORBIDDEN_FIELDS = {
    "host",
    "hostname",
    "ssh_user",
    "remote_user",
    "private_key",
    "password",
    "inventory",
    "inventory_path",
    "script_path",
    "path",
    "argv",
    "command",
    "deployment_profile",
    "execution_profile",
}


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    values: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            values.update(item.name for item in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            values.add(node.module)
    return values


def test_no_removed_ssh_domain_classes_are_restored() -> None:
    class_names: set[str] = set()
    for source in APP_ROOT.rglob("*.py"):
        tree = ast.parse(source.read_text(encoding="utf-8"))
        class_names.update(
            node.name for node in ast.walk(tree) if isinstance(node, ast.ClassDef)
        )
    assert not class_names & {
        "ServiceSSH",
        "SSHExecutor",
        "RemoteCommand",
        "CommandBuilder",
        "SSHConfig",
    }


def test_reasoning_and_interoperability_layers_do_not_import_ssh_implementation() -> None:
    violations = []
    for layer in PROTECTED:
        for source in layer.rglob("*.py"):
            for module in _imports(source):
                if "ansible" in module or "ssh" in module or module == "subprocess":
                    violations.append(f"{source.relative_to(APP_ROOT)}: {module}")
    assert not violations


def test_action_and_mcp_contracts_cannot_select_deployment_details() -> None:
    schema = ActionRequest.model_json_schema()
    action_fields = set(schema["properties"])
    for definition in schema.get("$defs", {}).values():
        action_fields.update(definition.get("properties", {}))
    mcp_fields = set(RemediationToolInput.model_json_schema()["properties"])
    llm_fields = set(InvestigationResult.__annotations__)
    assert not action_fields & FORBIDDEN_FIELDS
    assert not mcp_fields & FORBIDDEN_FIELDS
    assert not llm_fields & FORBIDDEN_FIELDS


def test_legacy_compatibility_adapter_can_only_enter_governed_proposal() -> None:
    source = (APP_ROOT / "adapters/legacy_api_application.py").read_text(encoding="utf-8")
    assert "WorkflowGovernedActionProposer" in source
    assert ".propose(" in source
    assert ".execute(" not in source
    assert ".dispatch_one(" not in source


def test_ansible_owns_ssh_transport_and_fixed_script_uses_argv() -> None:
    runner = (APP_ROOT / "adapters/ansible/runner.py").read_text(encoding="utf-8")
    playbook = (
        APP_ROOT / "deployment/playbooks/deployment_service_control.yml"
    ).read_text(encoding="utf-8")
    assert "ANSIBLE_PRIVATE_KEY_FILE" in runner
    assert "ansible.builtin.command" in playbook
    assert "argv:" in playbook
    assert "ansible.builtin.shell" not in playbook
