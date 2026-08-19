from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.executors.mock import MockExecutor
from app.services import operations as operations_module
from app.services.worker import WorkerService

ENV = "00000000-0000-0000-0000-000000000001"
DISABLED_ENV = "00000000-0000-0000-0000-000000000002"
SERVICE = "20000000-0000-0000-0000-000000000001"
OTHER_SERVICE = "20000000-0000-0000-0000-000000000002"
HOST_OK = "10000000-0000-0000-0000-000000000001"


def payload(**overrides: object) -> dict[str, object]:
    value: dict[str, object] = {
        "environment_id": ENV,
        "action": "status",
        "scope": "service_hosts",
        "service_id": SERVICE,
        "host_ids": [HOST_OK],
        "parameters": {},
    }
    value.update(overrides)
    return value


def test_create_task_returns_immediately_with_request_id(client: TestClient) -> None:
    result = client.post("/api/v1/operations", json=payload())
    assert result.status_code == 202
    body = result.json()
    assert body["request_id"] == result.headers["X-Request-ID"]
    assert body["data"]["status"] == "PENDING"
    task = client.get(f"/api/v1/tasks/{body['data']['task_id']}")
    assert task.json()["data"]["targets"][0]["host_name"].startswith("host-")


def test_rejects_special_character_injection(client: TestClient) -> None:
    result = client.post("/api/v1/operations", json=payload(parameters={"filter": "ok; rm -rf /"}))
    assert result.status_code == 422
    assert result.json()["error"]["code"] == "VALIDATION_ERROR"


def test_mock_start_creates_task_and_audit(
    client: TestClient,
    db: Session,
    mock_write_settings: Settings,
    monkeypatch,
) -> None:
    monkeypatch.setattr(operations_module, "get_settings", lambda: mock_write_settings)
    result = client.post(
        "/api/v1/operations",
        json=payload(action="start"),
        headers={"Idempotency-Key": "mock-start-success-0001"},
    )
    assert result.status_code == 202
    task_id = result.json()["data"]["task_id"]
    assert WorkerService(db, MockExecutor(), mock_write_settings).run_once()
    task = client.get(f"/api/v1/tasks/{task_id}").json()["data"]
    assert task["status"] == "SUCCEEDED"
    assert task["action"] == "start"
    assert task["targets"][0]["status"] == "SUCCEEDED"
    audits = client.get("/api/v1/audits").json()["data"]
    assert any(
        item["task_id"] == task_id and item["event_type"] == "TASK_CREATED" for item in audits
    )
    completed = next(item for item in audits if item["details"].get("result"))
    assert completed["details"]["execution_mode"] == "mock"


def test_mock_start_can_partially_fail(
    client: TestClient,
    db: Session,
    mock_write_settings: Settings,
    monkeypatch,
) -> None:
    monkeypatch.setattr(operations_module, "get_settings", lambda: mock_write_settings)
    created = client.post(
        "/api/v1/operations",
        json=payload(
            action="start",
            host_ids=[
                HOST_OK,
                "10000000-0000-0000-0000-000000000002",
            ],
        ),
        headers={"Idempotency-Key": "mock-start-partial-0001"},
    )
    assert created.status_code == 202
    task_id = created.json()["data"]["task_id"]
    assert WorkerService(db, MockExecutor(), mock_write_settings).run_once()

    task = client.get(f"/api/v1/tasks/{task_id}").json()["data"]
    assert task["status"] == "PARTIALLY_SUCCEEDED"
    assert {target["status"] for target in task["targets"]} == {"SUCCEEDED", "FAILED"}
    audits = client.get("/api/v1/audits").json()["data"]
    completed = next(
        item for item in audits if item["task_id"] == task_id and item["details"].get("result")
    )
    assert completed["details"]["result"] == "PARTIALLY_SUCCEEDED"


def test_rejects_unknown_action_as_structured_validation_error(
    client: TestClient,
) -> None:
    result = client.post("/api/v1/operations", json=payload(action="custom-shell"))
    assert result.status_code == 422
    assert result.json()["error"]["code"] == "REQUEST_VALIDATION_ERROR"


def test_rejects_disabled_environment(client: TestClient) -> None:
    result = client.post("/api/v1/operations", json=payload(environment_id=DISABLED_ENV))
    assert result.status_code == 422


def test_rejects_illegal_host(client: TestClient) -> None:
    result = client.post(
        "/api/v1/operations",
        json=payload(host_ids=["10000000-0000-0000-0000-999999999999"]),
    )
    assert result.status_code == 422


def test_rejects_undeployed_service_host_pair(client: TestClient) -> None:
    fail_host = "10000000-0000-0000-0000-000000000002"
    result = client.post(
        "/api/v1/operations", json=payload(service_id=OTHER_SERVICE, host_ids=[fail_host])
    )
    assert result.status_code == 422


def test_catalog_and_health_endpoints(client: TestClient) -> None:
    for path in ["environments", "services", "hosts", "tasks", "audits", "health", "ready"]:
        result = client.get(f"/api/v1/{path}")
        assert result.status_code == 200, path
        assert "request_id" in result.json()


def test_http_to_worker_to_target_result_and_audit(client: TestClient, db: Session) -> None:
    created = client.post(
        "/api/v1/operations",
        json=payload(
            host_ids=[
                HOST_OK,
                "10000000-0000-0000-0000-000000000002",
            ]
        ),
    )
    assert created.status_code == 202
    task_id = created.json()["data"]["task_id"]
    assert created.json()["data"]["status"] == "PENDING"

    assert WorkerService(db, MockExecutor()).run_once()

    detail = client.get(f"/api/v1/tasks/{task_id}")
    assert detail.status_code == 200
    task = detail.json()["data"]
    assert task["status"] == "PARTIALLY_SUCCEEDED"
    assert {target["status"] for target in task["targets"]} == {
        "SUCCEEDED",
        "FAILED",
    }
    assert all(target["duration_ms"] is not None for target in task["targets"])

    listed = client.get("/api/v1/tasks").json()["data"]
    assert next(item for item in listed if item["id"] == task_id)["targets"]

    audits = client.get("/api/v1/audits").json()["data"]
    task_audits = [item for item in audits if item["task_id"] == task_id]
    assert [item["event_type"] for item in reversed(task_audits)] == [
        "TASK_CREATED",
        "TASK_STATUS_CHANGED",
        "TASK_STATUS_CHANGED",
    ]
