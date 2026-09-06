from typing import Any

import pytest
from sqlalchemy.orm import Session

from app.adapters.git import FakeGitChangeProvider
from app.api.routes import changes
from app.change.service import ChangeService
from app.repositories.change_models import ChangeOutboxRecord

from .conftest import MANIFEST, intent, profile, seed_incident


def test_authenticated_api_previews_before_bound_approval(
    db: Session, client: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    seed_incident(db)
    git = FakeGitChangeProvider(base_files={profile().manifest_root: MANIFEST})
    monkeypatch.setattr(changes, "build_git_provider", lambda *_: git)
    monkeypatch.setattr(changes, "resolve_profile", lambda *_: profile())
    proposed = client.post("/api/v1/changes", json=intent().model_dump(mode="json"))
    assert proposed.status_code == 200, proposed.text
    change_id = proposed.json()["data"]["id"]
    preview = client.get(f"/api/v1/changes/{change_id}/preview")
    assert preview.status_code == 200, preview.text
    assert not git.branches
    # Missing and forged reviewed fingerprints never queue Git writes.
    missing = client.post(f"/api/v1/changes/{change_id}/approve", json={"reason": "Reviewed"})
    assert missing.status_code == 422
    forged = client.post(
        f"/api/v1/changes/{change_id}/approve",
        json={
            "reason": "Reviewed",
            "plan_fingerprint": "0" * 64,
        },
    )
    assert forged.status_code in {400, 422}
    assert db.query(ChangeOutboxRecord).count() == 0
    # The authenticated proposer cannot approve their own request, even with a valid plan.
    self_approval = client.post(
        f"/api/v1/changes/{change_id}/approve",
        json={
            "reason": "Reviewed",
            "plan_fingerprint": preview.json()["data"]["plan_fingerprint"],
        },
    )
    assert self_approval.status_code in {400, 422}
    assert not git.pull_requests


def test_api_approver_queues_exact_reviewed_plan(
    db: Session, client: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    seed_incident(db)
    git = FakeGitChangeProvider(base_files={profile().manifest_root: MANIFEST})
    monkeypatch.setattr(changes, "build_git_provider", lambda *_: git)
    record = ChangeService(db, git=git).propose(intent(), profile())
    assert client.post(f"/api/v1/changes/{record.id}/prepare").status_code == 200
    preview = client.get(f"/api/v1/changes/{record.id}/preview").json()["data"]
    result = client.post(
        f"/api/v1/changes/{record.id}/approve",
        json={
            "reason": "Reviewed current plan",
            "plan_fingerprint": preview["plan_fingerprint"],
        },
    )
    assert result.status_code == 200, result.text
    assert result.json()["data"]["status"] == "QUEUED"
    assert db.query(ChangeOutboxRecord).count() == 1
    assert not git.pull_requests
