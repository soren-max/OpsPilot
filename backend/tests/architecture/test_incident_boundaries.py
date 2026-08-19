import ast
from pathlib import Path

DOMAIN = Path(__file__).parents[2] / "app" / "domain" / "incidents"
FORBIDDEN = {"sqlalchemy", "fastapi", "subprocess", "ansible", "langgraph"}


def test_incident_domain_has_no_framework_or_execution_dependencies() -> None:
    violations: list[str] = []
    for source in DOMAIN.glob("*.py"):
        tree = ast.parse(source.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            module = ""
            if isinstance(node, ast.Import):
                modules = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                modules = [node.module or ""]
            else:
                continue
            for module in modules:
                if module.split(".")[0] in FORBIDDEN:
                    violations.append(f"{source.name}: {module}")
    assert not violations
