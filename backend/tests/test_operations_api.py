from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.adapters.mock import MockActionExecutor
from app.application import ActionService
from app.domain.actions.policy import ActionPolicyEngine
from app.services.worker import WorkerService

ENV = "00000000-0000-0000-0000-000000000001"
SERVICE = "20000000-0000-0000-0000-000000000001"
TARGET = "10000000-0000-0000-0000-000000000001"


def payload(**overrides: object) -> dict[str, object]:
    value: dict[str, object] = {
        "environment_id": ENV,
        "action": "status",
        "scope": "service_hosts",
        "service_id": SERVICE,
        "host_ids": [TARGET],
    }
    value.update(overrides)
    return value


def action_service() -> ActionService:
    return ActionService(
        ActionPolicyEngine(frozenset({"mock-host-ok", "mock-host-fail"})),
        MockActionExecutor(),
    )


def test_operations_runtime_routes_structured_status_through_action_core(
    client: TestClient, db: Session
) -> None:
    created = client.post("/api/v1/operations", json=payload())
    assert created.status_code == 202
    task_id = created.json()["data"]["task_id"]

    assert WorkerService(db, action_service()).run_once()

    task = client.get(f"/api/v1/tasks/{task_id}").json()["data"]
    assert task["status"] == "SUCCEEDED"
    assert task["targets"][0]["output"] == "Mock action get_service_status completed."
    assert task["targets"][0]["verification_status"] == "SUCCEEDED"


def test_structured_status_task_is_idempotent(client: TestClient) -> None:
    headers = {"Idempotency-Key": "portable-status-0001"}
    first = client.post("/api/v1/operations", json=payload(), headers=headers)
    replay = client.post("/api/v1/operations", json=payload(), headers=headers)

    assert first.status_code == replay.status_code == 202
    assert first.json()["data"]["task_id"] == replay.json()["data"]["task_id"]

    changed = client.post(
        "/api/v1/operations",
        json=payload(host_ids=["10000000-0000-0000-0000-000000000002"]),
        headers=headers,
    )
    assert changed.status_code == 409
    assert changed.json()["error"]["code"] == "IDEMPOTENCY_KEY_REUSED"


def test_operation_api_rejects_transport_and_arbitrary_execution_fields(
    client: TestClient,
) -> None:
    for field in ("executor", "playbook", "inventory", "ssh_user", "argv", "command"):
        response = client.post("/api/v1/operations", json=payload(**{field: "untrusted"}))
        assert response.status_code == 422, field


def test_operation_api_rejects_unbounded_change_actions(client: TestClient) -> None:
    for action in ("start", "stop", "deploy", "inspect_processes"):
        response = client.post("/api/v1/operations", json=payload(action=action))
        assert response.status_code in {403, 422}, action


def test_catalog_exposes_transport_agnostic_targets(client: TestClient) -> None:
    result = client.get(f"/api/v1/targets?environment_id={ENV}")
    assert result.status_code == 200
    target = result.json()["data"][0]
    assert {"id", "name", "environment_id", "description", "enabled", "labels"} <= target.keys()
    assert not {"address", "ssh_port", "ssh_username", "credential_reference"} & target.keys()


def test_catalog_and_health_endpoints(client: TestClient) -> None:
    for path in [
        "environments",
        "services",
        "hosts",
        "targets",
        "tasks",
        "audits",
        "health",
        "ready",
    ]:
        result = client.get(f"/api/v1/{path}")
        assert result.status_code == 200, path
        assert "request_id" in result.json()
