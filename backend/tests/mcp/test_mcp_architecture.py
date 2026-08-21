from pathlib import Path


def test_mcp_sdk_dependency_points_inward_only() -> None:
    root = Path(__file__).parents[2] / "app"
    forbidden = (root / "domain", root / "domain" / "actions", root / "workflows")
    for directory in forbidden:
        for path in directory.rglob("*.py"):
            source = path.read_text(encoding="utf-8")
            assert "import mcp" not in source
            assert "from mcp" not in source


def test_server_catalog_has_no_direct_execute_capability() -> None:
    from app.adapters.mcp.broker import McpCapabilityBroker

    assert "execute_action" not in McpCapabilityBroker.TOOL_ALLOWLIST
    assert "run_shell" not in McpCapabilityBroker.TOOL_ALLOWLIST
