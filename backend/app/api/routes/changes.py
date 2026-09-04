import json

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import response
from app.api.routes.auth import get_current_user
from app.change.runtime import build_git_provider
from app.change.service import ChangeDispatcher, ChangeService
from app.core.config import get_settings
from app.core.errors import ConflictError, ForbiddenError, NotFoundError, ValidationError
from app.db.session import get_db
from app.domain.change import GitOpsApplicationProfile
from app.models import User
from app.repositories.change_models import ChangeRecord
from app.repositories.changes import ChangeRepository
from app.repositories.incident_models import IncidentAuditEventRecord
from app.schemas_changes import ChangeDecision, ChangePage, ChangeRead
from app.services.rbac import require_permission

router = APIRouter(prefix="/changes", tags=["changes"])


def _record(db: Session, change_id: str) -> ChangeRecord:
    item = db.get(ChangeRecord, change_id)
    if item is None:
        raise NotFoundError("Change does not exist")
    return item


def _profile(item: ChangeRecord) -> GitOpsApplicationProfile:
    return GitOpsApplicationProfile.model_validate_json(json.dumps(item.profile_payload))


@router.get("")
def list_changes(
    request: Request,
    incident_id: str | None = None,
    limit: int = Query(default=100, ge=1, le=200),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, object]:
    require_permission(db, user, "incident.read")
    items = ChangeRepository(db).list(incident_id=incident_id, limit=limit)
    return response(
        request,
        ChangePage(items=[ChangeRead.model_validate(item) for item in items], count=len(items)),
    )


@router.get("/{change_id}")
def get_change(
    change_id: str,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, object]:
    require_permission(db, user, "incident.read")
    return response(request, ChangeRead.model_validate(_record(db, change_id)))


@router.get("/{change_id}/timeline")
def get_change_timeline(
    change_id: str,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, object]:
    require_permission(db, user, "incident.read")
    record = _record(db, change_id)
    events = list(
        db.scalars(
            select(IncidentAuditEventRecord)
            .where(IncidentAuditEventRecord.incident_id == record.incident_id)
            .order_by(IncidentAuditEventRecord.occurred_at)
        )
    )
    return response(
        request,
        [
            {
                "id": item.event_id,
                "event_type": item.event_type.value,
                "occurred_at": item.occurred_at,
                "summary": item.payload_summary,
                "metadata": item.event_metadata,
            }
            for item in events
            if item.event_metadata.get("change_id") == change_id
        ],
    )


@router.get("/{change_id}/preview")
def get_change_preview(
    change_id: str,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, object]:
    require_permission(db, user, "incident.read")
    record = _record(db, change_id)
    preview = ChangeService(db, git=None).preview(record)
    if preview is None:
        raise ConflictError("CHANGE_NOT_PLANNED", "Change preview is not available before approval")
    return response(request, preview)


@router.post("/{change_id}/approve")
async def approve_change(
    change_id: str,
    body: ChangeDecision,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, object]:
    require_permission(db, user, "incident.write")
    record = _record(db, change_id)
    try:
        git = build_git_provider(get_settings(), _profile(record))
        item = await ChangeService(db, git=git).approve(
            change_id, actor=user.username, reason=body.reason
        )
    except ValueError as exc:
        raise ValidationError(str(exc)) from exc
    return response(request, ChangeRead.model_validate(item))


@router.post("/{change_id}/reject")
def reject_change(
    change_id: str,
    body: ChangeDecision,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, object]:
    require_permission(db, user, "incident.write")
    try:
        item = ChangeService(db, git=None).reject(
            change_id, actor=user.username, reason=body.reason
        )
    except ValueError as exc:
        raise ValidationError(str(exc)) from exc
    return response(request, ChangeRead.model_validate(item))


@router.post("/{change_id}/reconcile")
async def reconcile_change(
    change_id: str,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, object]:
    require_permission(db, user, "incident.write")
    record = _record(db, change_id)
    try:
        git = build_git_provider(get_settings(), _profile(record))
        item = await ChangeDispatcher(db, git=git).reconcile_unknown(change_id)
    except ValueError as exc:
        raise ForbiddenError("CHANGE_RECONCILE_DENIED", str(exc)) from exc
    return response(request, ChangeRead.model_validate(item))
