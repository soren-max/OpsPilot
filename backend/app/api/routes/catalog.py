from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from app.api.deps import response
from app.api.routes.auth import get_current_user
from app.core.errors import NotFoundError
from app.db.session import get_db
from app.models import User
from app.repositories.catalog import CatalogRepository
from app.schemas import EnvironmentRead, HostRead, ServiceRead, TargetAssetRead
from app.services.rbac import require_permission

router = APIRouter(tags=["catalog"])


def service_read(repo: CatalogRepository, item: object) -> ServiceRead:
    value = ServiceRead.model_validate(item)
    value.host_count = len(item.deployments)  # type: ignore[attr-defined]
    value.current_status = repo.service_status(value.id)
    return value


def host_read(item: object) -> HostRead:
    value = HostRead.model_validate(item)
    value.service_count = len(item.deployments)  # type: ignore[attr-defined]
    return value


@router.get("/environments")
def environments(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, object]:
    require_permission(db, user, "service.read")
    environments = CatalogRepository(db).list_environments()
    items = [EnvironmentRead.model_validate(item) for item in environments]
    return response(request, items)


@router.get("/services")
def services(
    request: Request,
    environment_id: str | None = Query(default=None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, object]:
    require_permission(db, user, "service.read")
    repo = CatalogRepository(db)
    return response(
        request, [service_read(repo, item) for item in repo.list_services(environment_id)]
    )


@router.get("/services/{service_id}")
def service_detail(
    service_id: str,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, object]:
    require_permission(db, user, "service.read")
    repo = CatalogRepository(db)
    item = repo.get_service(service_id)
    if item is None:
        raise NotFoundError("Service does not exist")
    return response(request, service_read(repo, item))


@router.get("/services/{service_id}/hosts")
def service_hosts(
    service_id: str,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, object]:
    require_permission(db, user, "service.read")
    require_permission(db, user, "host.read")
    repo = CatalogRepository(db)
    item = repo.get_service(service_id)
    if item is None:
        raise NotFoundError("Service does not exist")
    return response(request, [host_read(deployment.host) for deployment in item.deployments])


@router.get("/hosts")
def hosts(
    request: Request,
    environment_id: str | None = Query(default=None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, object]:
    require_permission(db, user, "host.read")
    return response(
        request, [host_read(item) for item in CatalogRepository(db).list_hosts(environment_id)]
    )


@router.get("/targets")
def targets(
    request: Request,
    environment_id: str | None = Query(default=None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, object]:
    require_permission(db, user, "host.read")
    return response(
        request,
        [
            TargetAssetRead.model_validate(item)
            for item in CatalogRepository(db).list_hosts(environment_id)
        ],
    )


@router.get("/hosts/{host_id}")
def host_detail(
    host_id: str,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, object]:
    require_permission(db, user, "host.read")
    item = CatalogRepository(db).get_host(host_id)
    if item is None:
        raise NotFoundError("Host does not exist")
    return response(request, host_read(item))


@router.get("/hosts/{host_id}/services")
def host_services(
    host_id: str,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, object]:
    require_permission(db, user, "host.read")
    require_permission(db, user, "service.read")
    repo = CatalogRepository(db)
    item = repo.get_host(host_id)
    if item is None:
        raise NotFoundError("Host does not exist")
    return response(
        request, [service_read(repo, deployment.service) for deployment in item.deployments]
    )
