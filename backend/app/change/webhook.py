from __future__ import annotations

import hashlib
import hmac
import json
from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.base import utc_now
from app.repositories.change_models import ChangeRecord, GitEventInboxRecord

MAX_WEBHOOK_BYTES = 1_000_000
ALLOWED_EVENTS = frozenset({"pull_request", "pull_request_review", "push"})


class GitWebhookError(ValueError):
    pass


def verify_github_signature(body: bytes, secret: str, signature: str) -> None:
    if len(body) > MAX_WEBHOOK_BYTES:
        raise GitWebhookError("Webhook payload exceeds the bounded size")
    expected = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    if not signature.startswith("sha256=") or not hmac.compare_digest(expected, signature):
        raise GitWebhookError("Webhook signature is invalid")


def ingest_github_event(
    db: Session,
    *,
    body: bytes,
    secret: str,
    signature: str,
    delivery_id: str,
    event_type: str,
    allowed_repository: str,
    allowed_base_branch: str,
) -> bool:
    verify_github_signature(body, secret, signature)
    if event_type not in ALLOWED_EVENTS:
        raise GitWebhookError("Webhook event is not allowed")
    if not delivery_id or len(delivery_id) > 128:
        raise GitWebhookError("Webhook delivery ID is invalid")
    try:
        payload: dict[str, Any] = json.loads(body)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise GitWebhookError("Webhook payload is not valid JSON") from exc
    if not isinstance(payload, dict):
        raise GitWebhookError("Webhook payload must be an object")
    repository = payload.get("repository")
    repository_ref = repository.get("full_name") if isinstance(repository, dict) else None
    if repository_ref != allowed_repository:
        raise GitWebhookError("Webhook repository is outside the operator allowlist")
    pull = payload.get("pull_request")
    head = pull.get("head") if isinstance(pull, dict) else None
    base = pull.get("base") if isinstance(pull, dict) else None
    branch = head.get("ref") if isinstance(head, dict) else None
    if isinstance(pull, dict) and (
        not isinstance(base, dict) or base.get("ref") != allowed_base_branch
    ):
        raise GitWebhookError("Webhook base branch is outside operator scope")
    record = None
    if event_type in {"pull_request", "pull_request_review"} and not (
        isinstance(branch, str) and branch.startswith("opspilot/change/")
    ):
        raise GitWebhookError("Webhook pull request branch is outside the change namespace")
    if isinstance(branch, str):
        change_id = branch.removeprefix("opspilot/change/")
        record = db.get(ChangeRecord, change_id)
        if record is None or record.branch != branch:
            raise GitWebhookError("Webhook change correlation is invalid")
    if event_type == "push" and payload.get("ref") != f"refs/heads/{allowed_base_branch}":
        raise GitWebhookError("Webhook push branch is outside the operator base branch")
    item = GitEventInboxRecord(
        delivery_id=delivery_id,
        event_type=event_type,
        repository_ref=allowed_repository,
        change_id=record.id if record else None,
        received_at=utc_now(),
    )
    try:
        db.add(item)
        db.commit()
    except IntegrityError:
        db.rollback()
        return False
    return True
