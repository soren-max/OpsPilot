from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.orm import Session

from app.adapters.legacy_api import LegacyCompatibilityResult, LegacyRestartRequest
from app.adapters.legacy_api_application import LegacyApiCompatibilityAdapter
from app.adapters.mcp.application import WorkflowGovernedActionProposer
from app.api.deps import response
from app.api.routes.auth import get_current_user
from app.application.workflow_service import WorkflowService
from app.core.config import get_settings
from app.db.session import get_db
from app.execution.factory import build_execution_plane
from app.memory.factory import build_memory_store
from app.models import User
from app.services.rbac import require_permission
from app.worker import build_action_service, build_incident_capabilities, build_investigator

router = APIRouter(prefix="/legacy", tags=["legacy-compatibility"])


@router.post(
    "/service/restart",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=None,
)
async def restart_service(
    body: LegacyRestartRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, object]:
    """Translate a safe legacy call into the existing Policy/HITL workflow."""

    require_permission(db, user, "workflow.start")
    settings = get_settings()
    action_service = build_action_service(db, settings)
    execution_plane, dispatcher = build_execution_plane(db, settings, action_service)
    workflow = WorkflowService(
        db,
        investigator=build_investigator(settings),
        action_service=action_service,
        capabilities=build_incident_capabilities(db, settings, action_service),
        knowledge_retriever=build_memory_store(settings),
        execution_plane=execution_plane,
        execution_dispatcher=dispatcher,
    )
    result: LegacyCompatibilityResult = await LegacyApiCompatibilityAdapter(
        WorkflowGovernedActionProposer(db, workflow, action_service)
    ).propose_restart(body, actor=user.username)
    return response(request, result)
