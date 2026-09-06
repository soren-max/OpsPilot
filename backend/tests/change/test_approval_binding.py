from datetime import timedelta

import pytest
from sqlalchemy.orm import Session

from app.adapters.git import FakeGitChangeProvider
from app.change.service import ChangeDispatcher, ChangeService
from app.db.base import utc_now
from app.domain.change import ChangeStatus
from app.repositories.change_models import ChangeOutboxRecord

from .conftest import MANIFEST, intent, profile, seed_incident


@pytest.mark.asyncio
async def test_preview_binding_rejects_stale_review_then_accepts_refreshed_plan(
    db: Session,
) -> None:
    seed_incident(db)
    git = FakeGitChangeProvider(base_files={profile().manifest_root: MANIFEST})
    service = ChangeService(db, git=git)
    record = service.propose(intent(), profile())
    await service.prepare(record.id)
    preview = service.preview(record)
    assert preview is not None
    assert record.approval_id is None
    assert not git.branches
    git.base_revision = "c" * 40
    with pytest.raises(ValueError, match="Desired state changed"):
        await service.approve(
            record.id, actor="operator", reason="Reviewed", expected_plan=preview.plan_fingerprint
        )
    assert db.query(ChangeOutboxRecord).count() == 0
    await service.prepare(record.id)
    fresh = service.preview(record)
    assert fresh is not None
    with pytest.raises(ValueError, match="does not match"):
        await service.approve(
            record.id, actor="operator", reason="Reviewed", expected_plan=preview.plan_fingerprint
        )
    await service.approve(
        record.id, actor="operator", reason="Reviewed", expected_plan=fresh.plan_fingerprint
    )
    await service.approve(
        record.id, actor="operator", reason="Reviewed", expected_plan=fresh.plan_fingerprint
    )
    assert db.query(ChangeOutboxRecord).count() == 1
    assert record.status is ChangeStatus.QUEUED


@pytest.mark.asyncio
@pytest.mark.parametrize("stale", ["evidence", "approval", "base", "payload"])
async def test_dispatch_rechecks_authorization_before_any_git_write(
    db: Session, stale: str
) -> None:
    _, evidence = seed_incident(db)
    git = FakeGitChangeProvider(base_files={profile().manifest_root: MANIFEST})
    service = ChangeService(db, git=git)
    record = service.propose(intent(), profile())
    await service.approve(record.id, actor="operator", reason="Reviewed")
    if stale == "evidence":
        evidence.observed_at = utc_now() - timedelta(days=2)
    elif stale == "approval":
        record.approval_decided_at = utc_now() - timedelta(days=2)
    elif stale == "base":
        git.base_revision = "d" * 40
    else:
        record.change_set_payload = {
            **record.change_set_payload,
            "changed_files": {profile().manifest_root: "injected content"},
        }
    db.commit()
    assert await ChangeDispatcher(db, git=git).dispatch_one()
    assert record.status is ChangeStatus.REJECTED
    assert not git.branches
    assert not git.pull_requests
