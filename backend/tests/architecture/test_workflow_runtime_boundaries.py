import ast
from pathlib import Path

APP_ROOT = Path(__file__).parents[2] / "app"


def imported_modules(source: Path) -> set[str]:
    tree = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
    return modules


def imports_below(root: Path) -> dict[Path, set[str]]:
    return {
        source: imported_modules(source)
        for source in sorted(root.rglob("*.py"))
        if "__pycache__" not in source.parts
    }


def assert_no_import_prefix(root: Path, forbidden: tuple[str, ...]) -> None:
    violations = [
        f"{source.relative_to(APP_ROOT)}: {module}"
        for source, modules in imports_below(root).items()
        for module in modules
        if module.startswith(forbidden)
    ]
    assert not violations, "Workflow boundary violations:\n" + "\n".join(violations)


def test_domain_does_not_import_langgraph_or_executor_implementations() -> None:
    assert_no_import_prefix(APP_ROOT / "domain", ("langgraph", "app.adapters"))


def test_workflow_nodes_do_not_import_ansible_or_sqlalchemy() -> None:
    assert_no_import_prefix(
        APP_ROOT / "workflows" / "incident" / "nodes",
        ("app.adapters.ansible", "sqlalchemy"),
    )


def test_workflow_runtime_does_not_import_mock_backend() -> None:
    assert_no_import_prefix(
        APP_ROOT / "workflows" / "incident",
        ("app.adapters.mock",),
    )
