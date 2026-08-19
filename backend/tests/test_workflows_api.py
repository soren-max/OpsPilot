from sqlalchemy.orm import Session

from app.models import Permission, RolePermission


def create_incident(client: object) -> str:
    response = client.post(  # type: ignore[attr-defined]
        "/api/v1/incidents",
        json={
            "title": "API workflow incident",
            "summary": "Workflow API integration test",
            "severity": "HIGH",
            "environment": "test-mock",
            "service": "mock-service",
            "source": "pytest",
            "tags": [],
        },
    )
    assert response.status_code == 201
    return response.json()["data"]["id"]


def test_workflow_api_requires_auth_and_idempotency(client: object) -> None:
    incident_id = create_incident(client)
    missing_key = client.post(  # type: ignore[attr-defined]
        f"/api/v1/incidents/{incident_id}/workflows"
    )
    assert missing_key.status_code == 422

    authorization = client.headers.pop("Authorization")  # type: ignore[attr-defined]
    unauthorized = client.get(  # type: ignore[attr-defined]
        f"/api/v1/incidents/{incident_id}/workflows"
    )
    assert unauthorized.status_code == 401
    client.headers["Authorization"] = authorization  # type: ignore[attr-defined]


def test_workflow_api_enforces_rbac(client: object, db: Session) -> None:
    incident_id = create_incident(client)
    permission = db.query(Permission).filter_by(code="workflow.start").one()
    db.query(RolePermission).filter_by(permission_id=permission.id).delete()
    db.commit()

    response = client.post(  # type: ignore[attr-defined]
        f"/api/v1/incidents/{incident_id}/workflows",
        headers={"Idempotency-Key": "rbac-denied"},
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "PERMISSION_DENIED"


def test_workflow_api_start_list_detail_timeline_and_cancel(client: object) -> None:
    incident_id = create_incident(client)
    headers = {"Idempotency-Key": "api-workflow-1"}
    started = client.post(  # type: ignore[attr-defined]
        f"/api/v1/incidents/{incident_id}/workflows", headers=headers
    )
    assert started.status_code == 202
    workflow_id = started.json()["data"]["id"]
    duplicate = client.post(  # type: ignore[attr-defined]
        f"/api/v1/incidents/{incident_id}/workflows", headers=headers
    )
    assert duplicate.json()["data"]["id"] == workflow_id

    listed = client.get(  # type: ignore[attr-defined]
        f"/api/v1/incidents/{incident_id}/workflows"
    )
    assert [item["id"] for item in listed.json()["data"]] == [workflow_id]
    assert client.get(f"/api/v1/workflows/{workflow_id}").status_code == 200  # type: ignore[attr-defined]
    assert client.get(  # type: ignore[attr-defined]
        f"/api/v1/workflows/{workflow_id}/timeline"
    ).json()["data"] == []

    cancelled = client.post(f"/api/v1/workflows/{workflow_id}/cancel")  # type: ignore[attr-defined]
    assert cancelled.status_code == 200
    assert cancelled.json()["data"]["status"] == "CANCELLED"
