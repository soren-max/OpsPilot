from fastapi import APIRouter, Depends, Header, Request
from sqlalchemy.orm import Session

from app.api.deps import response
from app.change.webhook import MAX_WEBHOOK_BYTES, GitWebhookError, ingest_github_event
from app.core.config import get_settings
from app.core.errors import ForbiddenError, ValidationError
from app.db.session import get_db

router = APIRouter(prefix="/git/webhooks", tags=["git-webhooks"])


@router.post("/github")
async def github_webhook(
    request: Request,
    x_hub_signature_256: str = Header(default=""),
    x_github_delivery: str = Header(default=""),
    x_github_event: str = Header(default=""),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    settings = get_settings()
    if settings.github_webhook_secret is None or settings.github_repository is None:
        raise ForbiddenError("GIT_WEBHOOK_DISABLED", "GitHub webhook is not configured")
    body = b""
    async for chunk in request.stream():
        if len(body) + len(chunk) > MAX_WEBHOOK_BYTES:
            raise ValidationError("Webhook payload exceeds the bounded size")
        body += chunk
    try:
        accepted = ingest_github_event(
            db,
            body=body,
            secret=settings.github_webhook_secret.get_secret_value(),
            signature=x_hub_signature_256,
            delivery_id=x_github_delivery,
            event_type=x_github_event,
            allowed_repository=settings.github_repository,
            allowed_base_branch=settings.github_base_branch,
        )
    except GitWebhookError as exc:
        raise ValidationError(str(exc)) from exc
    return response(request, {"accepted": accepted, "duplicate": not accepted})
