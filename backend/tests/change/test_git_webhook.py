import hashlib
import hmac
import json

import pytest
from sqlalchemy.orm import Session

from app.change.webhook import GitWebhookError, ingest_github_event


def signed(payload: dict[str, object], secret: str = "webhook-secret") -> tuple[bytes, str]:
    body = json.dumps(payload).encode()
    signature = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return body, signature


def test_webhook_signature_and_delivery_dedupe(db: Session) -> None:
    body, signature = signed(
        {
            "repository": {"full_name": "synthetic/desired-state"},
            "ref": "refs/heads/main",
        }
    )
    kwargs = {
        "body": body,
        "secret": "webhook-secret",
        "signature": signature,
        "delivery_id": "delivery-1",
        "event_type": "push",
        "allowed_repository": "synthetic/desired-state",
        "allowed_base_branch": "main",
    }
    assert ingest_github_event(db, **kwargs)
    assert not ingest_github_event(db, **kwargs)


def test_forged_or_cross_repository_webhook_is_rejected(db: Session) -> None:
    body, signature = signed({"repository": {"full_name": "attacker/repo"}})
    with pytest.raises(GitWebhookError):
        ingest_github_event(
            db,
            body=body,
            secret="webhook-secret",
            signature=signature,
            delivery_id="delivery-2",
            event_type="pull_request",
            allowed_repository="synthetic/desired-state",
            allowed_base_branch="main",
        )
    with pytest.raises(GitWebhookError):
        ingest_github_event(
            db,
            body=body,
            secret="webhook-secret",
            signature="sha256=" + "0" * 64,
            delivery_id="delivery-3",
            event_type="push",
            allowed_repository="synthetic/desired-state",
            allowed_base_branch="main",
        )


def test_push_webhook_must_target_operator_base_branch(db: Session) -> None:
    body, signature = signed(
        {
            "repository": {"full_name": "synthetic/desired-state"},
            "ref": "refs/heads/untrusted",
        }
    )
    with pytest.raises(GitWebhookError, match="base branch"):
        ingest_github_event(
            db,
            body=body,
            secret="webhook-secret",
            signature=signature,
            delivery_id="delivery-wrong-branch",
            event_type="push",
            allowed_repository="synthetic/desired-state",
            allowed_base_branch="main",
        )
