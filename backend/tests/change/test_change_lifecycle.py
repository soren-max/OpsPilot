from __future__ import annotations

from datetime import timedelta

import pytest
from sqlalchemy.orm import Session

from app.adapters.git import FakeGitChangeProvider
from app.adapters.gitops import FakeGitOpsReconciler
from app.change.service import ChangeDispatcher, ChangeService, ChangeWatcher
from app.db.base import utc_now
from app.domain.change import ChangeStatus, GitOpsStatus
from app.repositories.change_models import ChangeOutboxRecord, ChangeOutboxStatus

from .conftest import MANIFEST, intent, profile, seed_incident


class Verifier:
    def __init__(self, result: bool) -> None:
        self.result = result

    async def verify(self, incident_id: str, verification_profile_ref: str) -> bool:
        assert incident_id == "incident-gitops-1"
        assert verification_profile_ref == "demo-api-health"
        return self.result


async def prepared_change(db: Session) -> tuple[object, FakeGitChangeProvider]:
    seed_incident(db)
    git = FakeGitChangeProvider(base_files={profile().manifest_root: MANIFEST})
    service = ChangeService(db, git=git)
    record = service.propose(intent(), profile())
    assert record.status is ChangeStatus.WAITING_APPROVAL
    await service.approve(record.id, actor="human-approver", reason="Evidence supports change")
    assert record.status is ChangeStatus.QUEUED
    assert record.approval_actor == "human-approver"
    assert record.approval_reason == "Evidence supports change"
    assert record.approval_decided_at is not None
    assert db.query(ChangeOutboxRecord).filter_by(change_id=record.id).count() == 1
    assert await ChangeDispatcher(db, git=git).dispatch_one()
    assert record.status is ChangeStatus.WAITING_REVIEW
    return record, git


@pytest.mark.asyncio
async def test_canonical_rollback_requires_two_gates_then_resolves(db: Session) -> None:
    record, git = await prepared_change(db)
    assert record.pull_request_id
    git.external_review(record.pull_request_id, approved=True)
    waiting_gitops = FakeGitOpsReconciler(
        GitOpsStatus(
            application_ref="demo-api-production",
            revision="old-revision",
            sync_status="OutOfSync",
            health_status="Healthy",
        )
    )
    watcher = ChangeWatcher(db, git=git, gitops=waiting_gitops, verifier=Verifier(True))
    await watcher.poll(record.id)
    assert record.status is ChangeStatus.APPROVED_FOR_MERGE
    # Review approval never merges through the OpsPilot provider.
    assert (await git.get_pull_request(record.pull_request_id)).merged_revision is None
    merged = git.external_merge(record.pull_request_id)
    await watcher.poll(record.id)
    assert record.status is ChangeStatus.RECONCILING
    waiting_gitops.status = waiting_gitops.status.model_copy(
        update={"revision": merged, "sync_status": "Synced", "health_status": "Healthy"}
    )
    await watcher.poll(record.id)
    assert record.status is ChangeStatus.RESOLVED
    assert record.verification_status == "SUCCEEDED"


@pytest.mark.asyncio
async def test_healthy_sync_does_not_resolve_when_verification_fails(db: Session) -> None:
    record, git = await prepared_change(db)
    assert record.pull_request_id
    git.external_review(record.pull_request_id, approved=True)
    merged = git.external_merge(record.pull_request_id)
    reconciler = FakeGitOpsReconciler(
        GitOpsStatus(
            application_ref="demo-api-production",
            revision=merged,
            sync_status="Synced",
            health_status="Healthy",
        )
    )
    await ChangeWatcher(db, git=git, gitops=reconciler, verifier=Verifier(False)).poll(record.id)
    assert record.status is ChangeStatus.FAILED
    assert record.verification_status == "FAILED"
    assert record.failure_category == "INDEPENDENT_VERIFICATION_FAILED"


@pytest.mark.asyncio
async def test_indeterminate_pr_creation_recovers_without_duplicate(db: Session) -> None:
    seed_incident(db)
    git = FakeGitChangeProvider(
        base_files={profile().manifest_root: MANIFEST}, create_pr_timeout_after_accept=True
    )
    service = ChangeService(db, git=git)
    record = service.propose(intent(), profile())
    await service.approve(record.id, actor="human-approver", reason="Evidence supports change")
    assert await ChangeDispatcher(db, git=git).dispatch_one()
    assert record.status is ChangeStatus.UNKNOWN
    outbox = db.query(ChangeOutboxRecord).filter_by(change_id=record.id).one()
    assert outbox.status is ChangeOutboxStatus.INDETERMINATE
    await ChangeDispatcher(db, git=git).reconcile_unknown(record.id)
    assert record.status is ChangeStatus.WAITING_REVIEW
    assert len(git.pull_requests) == 1


@pytest.mark.asyncio
async def test_expired_git_dispatch_lease_requires_reconciliation(db: Session) -> None:
    seed_incident(db)
    git = FakeGitChangeProvider(base_files={profile().manifest_root: MANIFEST})
    service = ChangeService(db, git=git)
    record = service.propose(intent(), profile())
    await service.approve(record.id, actor="human-approver", reason="Evidence supports change")
    outbox = db.query(ChangeOutboxRecord).filter_by(change_id=record.id).one()
    outbox.status = ChangeOutboxStatus.CLAIMED
    outbox.claimed_until = utc_now() - timedelta(seconds=1)
    db.commit()

    dispatcher = ChangeDispatcher(db, git=git)
    assert dispatcher.recover_expired_dispatches() == 1
    assert record.status is ChangeStatus.UNKNOWN
    assert outbox.status is ChangeOutboxStatus.INDETERMINATE
    assert not git.pull_requests


@pytest.mark.asyncio
async def test_unexpected_pr_head_fails_closed(db: Session) -> None:
    record, git = await prepared_change(db)
    assert record.pull_request_id
    pull = git.pull_requests[record.pull_request_id]
    git.pull_requests[record.pull_request_id] = pull.model_copy(update={"head_revision": "f" * 40})
    reconciler = FakeGitOpsReconciler(
        GitOpsStatus(
            application_ref="demo-api-production",
            revision=None,
            sync_status="OutOfSync",
            health_status="Unknown",
        )
    )
    await ChangeWatcher(db, git=git, gitops=reconciler, verifier=Verifier(True)).poll(record.id)
    assert record.status is ChangeStatus.RECONCILIATION_REQUIRED


@pytest.mark.asyncio
async def test_requester_cannot_self_approve(db: Session) -> None:
    seed_incident(db)
    git = FakeGitChangeProvider(base_files={profile().manifest_root: MANIFEST})
    record = ChangeService(db, git=git).propose(intent(), profile())
    with pytest.raises(ValueError, match="cannot approve"):
        await ChangeService(db, git=git).approve(
            record.id, actor="investigator", reason="Self approval must fail"
        )
    assert not git.pull_requests
