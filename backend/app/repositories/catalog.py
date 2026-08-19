from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session, selectinload

from app.models import Environment, Host, Service, ServiceDeployment


class CatalogRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list_environments(self) -> list[Environment]:
        return list(self.db.scalars(select(Environment).order_by(Environment.name)))

    def get_environment(self, environment_id: str) -> Environment | None:
        return self.db.get(Environment, environment_id)

    def list_services(self, environment_id: str | None = None) -> list[Service]:
        query: Select[tuple[Service]] = select(Service).options(selectinload(Service.deployments))
        if environment_id:
            query = query.where(Service.environment_id == environment_id)
        return list(self.db.scalars(query.order_by(Service.name)))

    def get_service(self, service_id: str) -> Service | None:
        return self.db.scalar(
            select(Service)
            .where(Service.id == service_id)
            .options(selectinload(Service.deployments).selectinload(ServiceDeployment.host))
        )

    def list_hosts(self, environment_id: str | None = None) -> list[Host]:
        query: Select[tuple[Host]] = select(Host).options(selectinload(Host.deployments))
        if environment_id:
            query = query.where(Host.environment_id == environment_id)
        return list(self.db.scalars(query.order_by(Host.name)))

    def get_host(self, host_id: str) -> Host | None:
        return self.db.scalar(
            select(Host)
            .where(Host.id == host_id)
            .options(selectinload(Host.deployments).selectinload(ServiceDeployment.service))
        )

    def deployments_query(self, environment_id: str) -> Select[tuple[ServiceDeployment]]:
        return (
            select(ServiceDeployment)
            .join(Service)
            .join(Host)
            .where(
                Service.environment_id == environment_id,
                Host.environment_id == environment_id,
                ServiceDeployment.enabled.is_(True),
                Service.enabled.is_(True),
                Host.enabled.is_(True),
            )
            .options(selectinload(ServiceDeployment.service), selectinload(ServiceDeployment.host))
        )

    def service_status(self, service_id: str) -> str:
        statuses = list(
            self.db.scalars(
                select(Host.last_status)
                .join(ServiceDeployment, ServiceDeployment.host_id == Host.id)
                .where(ServiceDeployment.service_id == service_id)
            )
        )
        if not statuses or all(value == "UNKNOWN" for value in statuses):
            return "UNKNOWN"
        if all(value == "RUNNING" for value in statuses):
            return "RUNNING"
        if all(value == "STOPPED" for value in statuses):
            return "STOPPED"
        if all(value == "UNAVAILABLE" for value in statuses):
            return "UNAVAILABLE"
        return "DEGRADED"

    def count_deployments(self, service_id: str | None = None, host_id: str | None = None) -> int:
        query = select(func.count(ServiceDeployment.id))
        if service_id:
            query = query.where(ServiceDeployment.service_id == service_id)
        if host_id:
            query = query.where(ServiceDeployment.host_id == host_id)
        return int(self.db.scalar(query) or 0)
