"""Deterministic controller: bounded ticks, no in-process human review waits."""

import asyncio
import json
import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.adapters.gitops import ArgoCDGitOpsReconciler
from app.capabilities import IncidentCapabilities
from app.change.runtime import build_git_provider, resolve_profile
from app.change.service import ChangeDispatcher, ChangeWatcher
from app.change.verification import CapabilityChangeVerifier
from app.core.config import Settings
from app.domain.change import ChangeStatus, GitOpsApplicationProfile
from app.repositories.change_models import ChangeOutboxRecord, ChangeOutboxStatus, ChangeRecord
from app.repositories.changes import ChangeRepository
from app.workflows.change import build_change_graph
from app.workflows.checkpoint import get_workflow_checkpointer

logger = logging.getLogger(__name__)


def tick(db: Session, settings: Settings, capabilities: IncidentCapabilities) -> int:
    if settings.gitops_provider == "disabled":
        return 0
    queued = list(
        db.scalars(
            select(ChangeRecord)
            .join(ChangeOutboxRecord)
            .where(
                ChangeOutboxRecord.status.in_(
                    {ChangeOutboxStatus.PENDING, ChangeOutboxStatus.CLAIMED}
                )
            )
            .limit(20)
        )
    )
    tracking = ChangeRepository(db).watching(limit=20)
    ids = list(dict.fromkeys(item.id for item in [*queued, *tracking]))
    handled = 0
    for change_id in ids:
        try:

            def advance(identity: str) -> str:
                return asyncio.run(
                    asyncio.wait_for(
                        process_change(db, settings, capabilities, identity), timeout=50
                    )
                )

            graph = build_change_graph(advance=advance, checkpointer=get_workflow_checkpointer())
            graph.invoke(
                {"change_id": change_id}, {"configurable": {"thread_id": f"change:{change_id}"}}
            )
            handled += 1
        except Exception:
            db.rollback()
            # Provider payloads and credentials must not enter logs. Next tick polls
            # again; an expired durable Git claim is recovered as UNKNOWN.
            logger.warning("Change controller observation unavailable: %s", change_id)
    return handled


async def process_change(
    db: Session, settings: Settings, capabilities: IncidentCapabilities, change_id: str
) -> str:
    record = db.get(ChangeRecord, change_id)
    if record is None:
        raise ValueError("Change does not exist")
    stored = GitOpsApplicationProfile.model_validate_json(json.dumps(record.profile_payload))
    current = resolve_profile(settings, stored.service, stored.environment)
    if current != stored:
        raise ValueError("Operator profile changed; explicit reconciliation required")
    git = build_git_provider(settings, current)
    dispatcher = ChangeDispatcher(db, git=git)
    dispatcher.recover_expired_dispatches()
    if record.status is ChangeStatus.QUEUED:
        await dispatcher.dispatch_one(change_id=change_id)
    elif record.status is ChangeStatus.UNKNOWN:
        await dispatcher.reconcile_unknown(change_id)
    elif record.pull_request_id is not None:
        assert settings.argocd_base_url and settings.argocd_token
        reconciler = ArgoCDGitOpsReconciler(
            settings.argocd_base_url,
            settings.argocd_token.get_secret_value(),
            frozenset({current.application_ref}),
        )
        verifier = CapabilityChangeVerifier(
            db, capabilities, profiles=frozenset({current.verification_profile_ref})
        )
        await ChangeWatcher(db, git=git, gitops=reconciler, verifier=verifier).poll(change_id)
    return record.status.value
