from pathlib import Path


def test_harness_dependency_stays_in_execution_adapter() -> None:
    root = Path(__file__).parents[2] / "app"
    forbidden = [root / "domain", root / "ai", root / "workflows", root / "adapters" / "mcp"]
    for directory in forbidden:
        for path in directory.rglob("*.py"):
            source = path.read_text(encoding="utf-8").lower()
            assert "adapters.execution.harness" not in source
            assert "harnesspipelineexecutionbackend" not in source


def test_execution_router_has_no_reasoning_or_transport_dependency() -> None:
    path = Path(__file__).parents[2] / "app" / "execution" / "router.py"
    source = path.read_text(encoding="utf-8").lower()
    for forbidden in ("llm", "openai", "mcp", "httpx", "harness"):
        assert forbidden not in source


def test_external_contract_cannot_name_backend_or_pipeline() -> None:
    from app.domain.actions.models import ActionRequest

    fields = set(ActionRequest.model_json_schema()["properties"])
    assert fields.isdisjoint({"backend", "profile", "pipeline", "pipeline_id", "provider_url"})


def test_outbox_claim_uses_postgres_skip_locked() -> None:
    path = Path(__file__).parents[2] / "app" / "repositories" / "executions.py"
    source = path.read_text(encoding="utf-8")
    assert "with_for_update(skip_locked=True)" in source
    assert "OutboxStatus.PENDING" in source
