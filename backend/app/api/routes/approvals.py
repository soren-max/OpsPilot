from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from app.api.deps import response
from app.api.routes.auth import get_current_user
from app.application.approval_service import ApprovalService
from app.application.workflow_service import WorkflowService
from app.core.config import get_settings
from app.db.session import get_db
from app.domain.approvals import ApprovalActor
from app.models import User
from app.schemas_approvals import ApprovalDecisionCreate, ApprovalRequestRead
from app.services.rbac import require_permission
from app.worker import build_action_service

router = APIRouter(prefix="/approvals", tags=["approvals"])


def _actor(user: User) -> ApprovalActor:
    return ApprovalActor(actor_id=user.id, display_name=user.display_name)


@router.get("")
def list_approvals(
    request: Request,
    incident_id: str | None = Query(default=None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, object]:
    require_permission(db, user, "approval.read")
    items = ApprovalService(db).list(incident_id)
    return response(request, [ApprovalRequestRead.model_validate(item) for item in items])


def _decide_and_resume(
    approval_id: str,
    body: ApprovalDecisionCreate,
    db: Session,
    user: User,
    *,
    approve: bool,
) -> ApprovalRequestRead:
    require_permission(db, user, "approval.decide")
    approvals = ApprovalService(db)
    item = (
        approvals.approve(approval_id, _actor(user), body.reason)
        if approve
        else approvals.reject(approval_id, _actor(user), body.reason)
    )
    WorkflowService(
        db, action_service=build_action_service(db, get_settings())
    ).resume(item.id)
    return ApprovalRequestRead.model_validate(approvals.get(item.id))


@router.post("/{approval_id}/approve")
def approve(
    approval_id: str,
    body: ApprovalDecisionCreate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, object]:
    return response(request, _decide_and_resume(approval_id, body, db, user, approve=True))


@router.post("/{approval_id}/reject")
def reject(
    approval_id: str,
    body: ApprovalDecisionCreate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, object]:
    return response(request, _decide_and_resume(approval_id, body, db, user, approve=False))
