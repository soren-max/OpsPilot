from fastapi.testclient import TestClient


def test_health_reports_application_readiness(client: TestClient) -> None:
    body = client.get("/api/v1/health").json()["data"]
    assert body == {"status": "ok", "application": "ready"}
    assert client.get("/health").json()["data"] == body


def test_ready_reports_generic_execution_backend(client: TestClient) -> None:
    body = client.get("/api/v1/ready").json()["data"]
    assert body == {
        "status": "ready",
        "application": "ready",
        "database": "ready",
        "execution_backend": {"backend": "mock", "available": True},
    }
    serialized = str(body).lower()
    assert "services.sh" not in serialized
    assert "ssh" not in serialized
