from sqlalchemy.orm import Session

from app.models import Permission, RolePermission


def create_incident(client: object, **overrides: object) -> object:
    body: dict[str, object] = {
        "title": "API latency",
        "summary": "Latency exceeded SLO",
        "severity": "HIGH",
        "environment": "test-mock",
        "service": "checkout",
        "source": "operator",
        "tags": ["api"],
    }
    body.update(overrides)
    return client.post("/api/v1/incidents", json=body)  # type: ignore[attr-defined, no-any-return]


def test_incident_api_pagination_filter_and_timeline(client: object) -> None:
    first = create_incident(client)
    create_incident(client, title="Worker saturation", severity="CRITICAL", service="worker")
    assert first.status_code == 201  # type: ignore[attr-defined]

    page = client.get(  # type: ignore[attr-defined]
        "/api/v1/incidents?severity=HIGH&service=checkout&offset=0&limit=1"
    )
    assert page.status_code == 200
    assert page.json()["data"]["count"] == 1
    paged = client.get("/api/v1/incidents?offset=0&limit=1")  # type: ignore[attr-defined]
    assert len(paged.json()["data"]["items"]) == 1
    assert paged.json()["data"]["count"] == 2
    incident_id = first.json()["data"]["id"]  # type: ignore[attr-defined]
    timeline = client.get(f"/api/v1/incidents/{incident_id}/timeline")  # type: ignore[attr-defined]
    assert timeline.status_code == 200
    assert timeline.json()["data"][0]["event_type"] == "INCIDENT_CREATED"
    related = client.get(f"/api/v1/incidents/{incident_id}/related")  # type: ignore[attr-defined]
    assert related.status_code == 200
    assert related.json()["data"] == []


def test_incident_routes_enforce_rbac(client: object, db: Session) -> None:
    permission = db.query(Permission).filter_by(code="incident.read").one()
    db.query(RolePermission).filter_by(permission_id=permission.id).delete()
    db.commit()

    response = client.get("/api/v1/incidents")  # type: ignore[attr-defined]

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "PERMISSION_DENIED"
