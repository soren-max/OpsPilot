from fastapi import APIRouter, Depends, Header, Request, status
from sqlalchemy.orm import Session

from app.api.deps import response
from app.api.routes.auth import get_current_user
from app.application.workflow_service import WorkflowService
from app.db.session import get_db
from app.models import User
from app.schemas_workflows import WorkflowRunRead
from app.services.rbac import require_permission

incident_router = APIRouter(prefix="/incidents", tags=["workflows"])
workflow_router = APIRouter(prefix="/workflows", tags=["workflows"])


@incident_router.post(
    "/{incident_id}/workflows", status_code=status.HTTP_202_ACCEPTED
)
def start_workflow(
    incident_id: str,
    request: Request,
    idempotency_key: str = Header(min_length=1, max_length=128, alias="Idempotency-Key"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, object]:
    require_permission(db, user, "workflow.start")
    item = WorkflowService(db).start(incident_id, user.username, idempotency_key)
    return response(request, WorkflowRunRead.model_validate(item))


@incident_router.get("/{incident_id}/workflows")
def list_workflows(
    incident_id: str,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, object]:
    require_permission(db, user, "workflow.read")
    items = WorkflowService(db).list_for_incident(incident_id)
    return response(request, [WorkflowRunRead.model_validate(item) for item in items])


@workflow_router.get("/{workflow_id}")
def get_workflow(
    workflow_id: str,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, object]:
    require_permission(db, user, "workflow.read")
    item = WorkflowService(db).get(workflow_id)
    return response(request, WorkflowRunRead.model_validate(item))


@workflow_router.get("/{workflow_id}/timeline")
def workflow_timeline(
    workflow_id: str,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, object]:
    require_permission(db, user, "workflow.read")
    return response(request, WorkflowService(db).timeline(workflow_id))


@workflow_router.post("/{workflow_id}/cancel")
def cancel_workflow(
    workflow_id: str,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, object]:
    require_permission(db, user, "workflow.cancel")
    item = WorkflowService(db).cancel(workflow_id)
    return response(request, WorkflowRunRead.model_validate(item))
