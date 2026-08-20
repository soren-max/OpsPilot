import ast
from pathlib import Path

APP_ROOT = Path(__file__).parents[2] / "app"


def imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
    return modules


def sources(root: Path) -> list[Path]:
    return sorted(path for path in root.rglob("*.py") if "__pycache__" not in path.parts)


def test_domain_has_no_observability_or_orchestration_dependencies() -> None:
    forbidden = ("httpx", "langgraph", "app.adapters", "app.capabilities", "mcp")
    violations = [
        f"{path.relative_to(APP_ROOT)}: {module}"
        for path in sources(APP_ROOT / "domain")
        for module in imports(path)
        if module.startswith(forbidden)
    ]
    assert not violations, "Domain dependency violations:\n" + "\n".join(violations)


def test_capability_ports_do_not_import_implementations() -> None:
    ports = sources(APP_ROOT / "capabilities")
    violations = [
        f"{path.relative_to(APP_ROOT)}: {module}"
        for path in ports
        if path.name == "port.py"
        for module in imports(path)
        if module.startswith(("app.adapters", "httpx", "sqlalchemy", "langgraph"))
    ]
    assert not violations, "Capability port violations:\n" + "\n".join(violations)


def test_workflow_nodes_do_not_import_observability_adapters() -> None:
    violations = [
        f"{path.relative_to(APP_ROOT)}: {module}"
        for path in sources(APP_ROOT / "workflows" / "incident" / "nodes")
        for module in imports(path)
        if module.startswith(("app.adapters", "httpx", "sqlalchemy"))
    ]
    assert not violations, "Workflow node violations:\n" + "\n".join(violations)


def test_typed_queries_expose_no_raw_query_language_or_backend_url() -> None:
    from app.capabilities.logs import LogQuery
    from app.capabilities.metrics import MetricQuery

    fields = set(MetricQuery.model_fields) | set(LogQuery.model_fields)
    assert not fields & {"raw_promql", "raw_logql", "base_url", "tenant", "headers"}
