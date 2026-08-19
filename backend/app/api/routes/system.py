from fastapi import APIRouter, Depends, Request
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.deps import response
from app.core.config import get_settings
from app.db.session import get_db
from app.services.readiness import execution_backend_readiness

router = APIRouter(tags=["system"])


@router.get("/health")
def health(request: Request) -> dict[str, object]:
    return response(request, {"status": "ok", "application": "ready"})


@router.get("/ready")
def ready(request: Request, db: Session = Depends(get_db)) -> dict[str, object]:
    db.execute(text("SELECT 1"))
    backend = execution_backend_readiness(get_settings())
    return response(
        request,
        {
            "status": "ready" if backend["available"] else "not_ready",
            "application": "ready",
            "database": "ready",
            "execution_backend": backend,
        },
    )
