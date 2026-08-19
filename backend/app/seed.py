import argparse

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.bootstrap.seed_users import seed_default_admin
from app.core.config import Settings, get_settings
from app.core.enums import EnvironmentLevel
from app.db.session import SessionLocal
from app.models import (
    Environment,
    Host,
    OperationRequest,
    OperationTask,
    Service,
    ServiceDeployment,
)


def _reset_catalog(db: Session) -> None:
    task_count = db.scalar(select(func.count()).select_from(OperationTask)) or 0
    request_count = db.scalar(select(func.count()).select_from(OperationRequest)) or 0
    if task_count or request_count:
        raise RuntimeError(
            "--reset refuses to remove a catalog referenced by operation/approval history; "
            "archive the database and initialize a reviewed empty database instead"
        )
    for model in (ServiceDeployment, Service, Host, Environment):
        db.execute(delete(model))
    db.commit()


def _integration_catalog_ready(db: Session, settings: Settings) -> bool:
    environment_code = sorted(settings.allowed_environment_set)[0]
    environment = db.scalar(select(Environment).where(Environment.code == environment_code))
    if environment is None:
        return False
    hosts = set(db.scalars(select(Host.name).where(Host.environment_id == environment.id)))
    services = set(db.scalars(select(Service.name).where(Service.environment_id == environment.id)))
    deployed_hosts = set(
        db.scalars(
            select(Host.name)
            .join(ServiceDeployment, ServiceDeployment.host_id == Host.id)
            .where(Host.environment_id == environment.id)
        )
    )
    deployed_services = set(
        db.scalars(
            select(Service.name)
            .join(ServiceDeployment, ServiceDeployment.service_id == Service.id)
            .where(Service.environment_id == environment.id)
        )
    )
    return (
        settings.allowed_host_set <= hosts
        and settings.allowed_service_set <= services
        and settings.allowed_host_set <= deployed_hosts
        and settings.allowed_service_set <= deployed_services
    )


def seed(*, reset: bool = False) -> None:
    with SessionLocal() as db:
        settings = get_settings()
        seed_default_admin(db, settings)
        if reset:
            _reset_catalog(db)
        if settings.real_integration_execution_enabled:
            environment_code = sorted(settings.allowed_environment_set)[0]
            existing = db.scalar(select(Environment).where(Environment.code == environment_code))
            if existing is not None:
                if _integration_catalog_ready(db, settings):
                    print("Integration-test allowlisted catalog already exists; no changes made.")
                    return
                raise RuntimeError(
                    "Integration-test catalog exists but does not match the configured allowlists; "
                    "review the database backup and run `python -m app.seed --reset`"
                )
            environment = Environment(
                name="隔离测试环境 · 受控本地执行",
                code=environment_code,
                enabled=True,
                description="仅允许经评审的白名单 services.sh 目标",
                environment_level=EnvironmentLevel.TEST,
            )
            services = [
                Service(
                    name=name,
                    service_type="integration-test",
                    is_middleware=False,
                    description="隔离测试 dummy service",
                    environment=environment,
                )
                for name in sorted(settings.allowed_service_set)
            ]
            hosts = [
                Host(
                    name=name,
                    description="隔离测试目标（白名单）",
                    mock_behavior="success",
                    environment=environment,
                )
                for name in sorted(settings.allowed_host_set)
            ]
            db.add_all([environment, *services, *hosts])
            db.flush()
            db.add_all(
                [
                    ServiceDeployment(service=service, host=host)
                    for service in services
                    for host in hosts
                ]
            )
            db.commit()
            print("Integration-test allowlisted seed data created.")
            return
        if db.scalar(select(Environment.id).limit(1)):
            print("Seed data already exists; no changes made.")
            return
        environment = Environment(
            name="外网模拟环境",
            code="public-mock",
            enabled=True,
            description="仅用于安全 MVP 的模拟环境，不映射任何真实内网",
            environment_level=EnvironmentLevel.DEVELOPMENT,
        )
        disabled = Environment(
            name="停用演示环境",
            code="disabled-mock",
            enabled=False,
            description="用于环境启用校验测试",
            environment_level=EnvironmentLevel.DEVELOPMENT,
        )
        hosts = [
            Host(name="mock-host-a", description="稳定模拟节点", mock_behavior="success"),
            Host(name="mock-host-b", description="失败模拟节点", mock_behavior="failure"),
            Host(name="mock-host-c", description="超时模拟节点", mock_behavior="timeout"),
        ]
        services = [
            Service(
                name="gateway-service",
                service_type="application",
                is_middleware=False,
                description="模拟网关服务",
            ),
            Service(
                name="workflow-service",
                service_type="application",
                is_middleware=False,
                description="模拟流程服务",
            ),
            Service(
                name="message-middleware",
                service_type="middleware",
                is_middleware=True,
                description="模拟中间件",
            ),
        ]
        for host in hosts:
            host.environment = environment
        for service in services:
            service.environment = environment
        db.add_all([environment, disabled, *hosts, *services])
        db.flush()
        deployments = [
            ServiceDeployment(service=services[0], host=hosts[0]),
            ServiceDeployment(service=services[0], host=hosts[1]),
            ServiceDeployment(service=services[1], host=hosts[0]),
            ServiceDeployment(service=services[1], host=hosts[2]),
            ServiceDeployment(service=services[2], host=hosts[0]),
        ]
        db.add_all(deployments)
        db.commit()
        print("Mock seed data created.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Initialize the OPSPILOT catalog safely")
    parser.add_argument(
        "--reset",
        action="store_true",
        help="replace an unreferenced demo catalog before seeding the configured mode",
    )
    args = parser.parse_args()
    seed(reset=args.reset)
