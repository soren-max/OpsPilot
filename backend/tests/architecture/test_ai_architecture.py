import ast
from pathlib import Path

from app.ai.models import InvestigationModelOutput

APP_ROOT = Path(__file__).parents[2] / "app"


def imported_modules(root: Path) -> list[tuple[Path, str]]:
    found: list[tuple[Path, str]] = []
    for path in root.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                found.extend((path, alias.name) for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                found.append((path, node.module))
    return found


def test_llm_dependencies_do_not_cross_authorization_boundaries() -> None:
    protected = [APP_ROOT / "domain", APP_ROOT / "executors", APP_ROOT / "capabilities"]
    violations = [
        f"{path.relative_to(APP_ROOT)}: {module}"
        for root in protected
        if root.exists()
        for path, module in imported_modules(root)
        if module.startswith(("openai", "app.ai"))
    ]
    assert not violations


def test_llm_investigator_cannot_reach_execution_implementations() -> None:
    forbidden = ("subprocess", "app.adapters.ansible", "app.executors")
    violations = [
        f"{path.relative_to(APP_ROOT)}: {module}"
        for path, module in imported_modules(APP_ROOT / "ai")
        if module.startswith(forbidden)
    ]
    assert not violations


def test_model_output_has_no_authorization_or_tool_fields() -> None:
    fields = set(InvestigationModelOutput.model_fields)
    assert not fields & {
        "approval", "approved", "executor", "tool_call", "shell_command", "playbook",
        "inventory", "promql", "logql", "credential", "risk_override",
    }
