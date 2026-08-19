import logging
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api.routes import auth, catalog, incidents, operations, system
from app.bootstrap.seed_users import seed_default_admin
from app.core.config import get_settings
from app.core.errors import AppError, ForbiddenError
from app.core.logging import configure_logging
from app.db.session import SessionLocal
from app.services.audit import write_audit

settings = get_settings()
configure_logging(settings.log_level, settings.log_file)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    logger.info(
        "OpsPilot API starting with executor=%s dry_run_only=%s",
        settings.selected_executor,
        settings.dry_run_only,
    )
    db = SessionLocal()
    try:
        seed_default_admin(db, settings)
        if settings.default_admin_enabled and len(settings.default_admin_password) < 16:
            logger.warning("检测到较弱的初始管理员凭据配置，请在正式部署前修改。")
    finally:
        db.close()
    yield
    logger.info("OpsPilot API stopped")


app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "OPTIONS"],
    allow_headers=[
        "Content-Type",
        "Authorization",
        "X-Request-ID",
        "Idempotency-Key",
    ],
)


@app.middleware("http")
async def request_id_middleware(request: Request, call_next: Any) -> Any:
    incoming = request.headers.get("X-Request-ID", "")
    request_id = incoming if len(incoming) <= 64 and incoming.isascii() else ""
    request.state.request_id = request_id or str(uuid.uuid4())
    response_value = await call_next(request)
    response_value.headers["X-Request-ID"] = request.state.request_id
    return response_value


@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    _audit_rejection(request, exc.code, exc.message)
    if "/auth/" in request.url.path:
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "code": exc.code,
                "message": exc.message,
                "request_id": request.state.request_id,
            },
        )
    content: dict[str, Any] = {
        "request_id": request.state.request_id,
        "error": {"code": exc.code, "message": exc.message, "details": exc.details},
    }
    if isinstance(exc, ForbiddenError):
        details = exc.details if isinstance(exc.details, dict) else {}
        content.update(
            {
                "success": False,
                "error_code": exc.code,
                "message": exc.message,
                "action": details.get("action"),
            }
        )
    return JSONResponse(status_code=exc.status_code, content=content)


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    _audit_rejection(request, "REQUEST_VALIDATION_ERROR", "Request validation failed")
    if "/auth/" in request.url.path:
        return JSONResponse(
            status_code=422,
            content={
                "code": "REQUEST_VALIDATION_ERROR",
                "message": "登录请求无效",
                "request_id": request.state.request_id,
            },
        )
    return JSONResponse(
        status_code=422,
        content={
            "request_id": request.state.request_id,
            "error": {
                "code": "REQUEST_VALIDATION_ERROR",
                "message": "Request validation failed",
                # Pydantic includes the rejected input by default. Never reflect
                # request values because rejected input may contain secrets.
                "details": [
                    {
                        "type": item.get("type"),
                        "loc": item.get("loc"),
                        "msg": item.get("msg"),
                    }
                    for item in exc.errors()
                ],
            },
        },
    )


def _audit_rejection(request: Request, code: str, message: str) -> None:
    db = SessionLocal()
    try:
        write_audit(
            db,
            "REQUEST_REJECTED",
            getattr(request.state, "actor", "anonymous"),
            "HTTP request rejected",
            details={
                "error_code": code,
                "rejection_reason": message,
                "path": request.url.path,
                "request_id": request.state.request_id,
            },
        )
        db.commit()
    except Exception:
        db.rollback()
        logger.exception("Unable to persist rejection audit")
    finally:
        db.close()


app.include_router(auth.router, prefix="/api/v1")
app.include_router(system.router, prefix="/api/v1")
# Operational probes also have stable unversioned paths for systemd/proxies.
app.include_router(system.router, include_in_schema=False)
app.include_router(catalog.router, prefix="/api/v1")
app.include_router(operations.router, prefix="/api/v1")
app.include_router(incidents.router, prefix="/api/v1")


# The offline package places the already-built Vite application beside backend/.
# OPSPILOT_FRONTEND_DIST remains available for integrators that use a different layout.
_frontend_dist = Path(
    __import__("os").environ.get(
        "OPSPILOT_FRONTEND_DIST", str(Path(__file__).resolve().parents[2] / "frontend" / "dist")
    )
).resolve()
if _frontend_dist.is_dir():
    app.mount("/assets", StaticFiles(directory=_frontend_dist / "assets"), name="frontend-assets")

    @app.get("/", include_in_schema=False)
    @app.get("/{path:path}", include_in_schema=False)
    def frontend(path: str = "") -> FileResponse:
        """Serve the SPA entry point; API routes above take precedence."""
        candidate = (_frontend_dist / path).resolve()
        if path and candidate.is_file() and _frontend_dist in candidate.parents:
            return FileResponse(candidate)
        return FileResponse(_frontend_dist / "index.html")
