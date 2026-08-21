from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import response
from app.api.routes.auth import get_current_user
from app.core.errors import NotFoundError
from app.db.session import get_db
from app.models import User
from app.repositories.execution_models import ExecutionRecord
from app.schemas_executions import ExecutionRead
from app.services.rbac import require_permission

router = APIRouter(prefix="/executions", tags=["executions"])


@router.get("")
def list_executions(
    request: Request,
    incident_id: str | None = None,
    limit: int = Query(default=100, ge=1, le=200),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, object]:
    require_permission(db, user, "incident.read")
    query = select(ExecutionRecord).order_by(ExecutionRecord.created_at.desc()).limit(limit)
    if incident_id:
        query = query.where(ExecutionRecord.incident_id == incident_id)
    items = [ExecutionRead.model_validate(item) for item in db.scalars(query)]
    return response(request, items)


@router.get("/{execution_id}")
def get_execution(
    execution_id: str,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, object]:
    require_permission(db, user, "incident.read")
    item = db.get(ExecutionRecord, execution_id)
    if item is None:
        raise NotFoundError("Execution does not exist")
    return response(request, ExecutionRead.model_validate(item))
