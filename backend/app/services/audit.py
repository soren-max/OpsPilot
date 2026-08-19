from typing import Any

from sqlalchemy.orm import Session

from app.db.base import utc_now
from app.models import AuditLog
from app.services.redaction import redact_account, redact_details, redact_text


def write_audit(
    db: Session,
    event_type: str,
    actor: str,
    message: str,
    task_id: str | None = None,
    details: dict[str, Any] | None = None,
) -> None:
    db.add(
        AuditLog(
            task_id=task_id,
            event_type=event_type,
            actor=redact_account(actor),
            message=redact_text(message) or "",
            details=redact_details(details or {}),
            created_at=utc_now(),
        )
    )
