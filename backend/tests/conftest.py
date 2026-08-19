import asyncio
import os
import uuid
from collections.abc import Generator
from pathlib import Path

import anyio.to_thread
import httpx
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

os.environ["OPSPILOT_DATABASE_URL"] = "sqlite:///./test.db"
os.environ["OPSPILOT_SECRET_KEY"] = "test-only-secret-key-not-for-deployment"
os.environ["DEFAULT_ADMIN_PASSWORD"] = "admin123-test-only"
os.environ["DEFAULT_ADMIN_ENABLED"] = "true"
os.environ["OPSPILOT_ALLOWED_ENVIRONMENTS"] = "test-mock"
os.environ["OPSPILOT_ALLOWED_HOSTS"] = "mock-host-ok,mock-host-fail,mock-host-timeout"
os.environ["OPSPILOT_ALLOWED_SERVICES"] = "mock-service,other-service"

from app.bootstrap.seed_users import seed_default_admin
from app.core.config import Settings, get_settings
from app.core.enums import EnvironmentLevel
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models import Environment, Host, Service, ServiceDeployment


async def _run_sync_inline(
    func: object,
    *args: object,
    abandon_on_cancel: bool = False,
    cancellable: bool | None = None,
    limiter: object | None = None,
) -> object:
    """Run sync endpoints inline where the managed sandbox cannot spawn threads."""
    del abandon_on_cancel, cancellable, limiter
    return func(*args)  # type: ignore[operator]


anyio.to_thread.run_sync = _run_sync_inline  # type: ignore[assignment]

TEST_DATABASE = Path("/tmp") / f"opspilot-tests-{uuid.uuid4().hex}.db"
engine = create_engine(
    f"sqlite:///{TEST_DATABASE.as_posix()}", connect_args={"check_same_thread": False}
)
TestingSession = sessionmaker(bind=engine, expire_on_commit=False, class_=Session)


def _reset_database() -> None:
    """Drop fixture tables safely even when a failed test left FK rows behind."""
    with engine.connect() as connection:
        connection.exec_driver_sql("PRAGMA foreign_keys=OFF")
        Base.metadata.drop_all(connection)
        connection.exec_driver_sql("PRAGMA foreign_keys=ON")
        connection.commit()


class SyncASGIClient:
    """Small synchronous facade over httpx's ASGI transport for Python 3.13 tests."""

    def __init__(self) -> None:
        self.headers: dict[str, str] = {}

    def request(self, method: str, path: str, **kwargs: object) -> httpx.Response:
        async def send() -> httpx.Response:
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(
                transport=transport,
                base_url="http://testserver",
                headers=self.headers,
            ) as asgi_client:
                return await asgi_client.request(method, path, **kwargs)

        return asyncio.run(send())

    def get(self, path: str, **kwargs: object) -> httpx.Response:
        return self.request("GET", path, **kwargs)

    def post(self, path: str, **kwargs: object) -> httpx.Response:
        return self.request("POST", path, **kwargs)

    def put(self, path: str, **kwargs: object) -> httpx.Response:
        return self.request("PUT", path, **kwargs)

    def close(self) -> None:
        return None


@pytest.fixture(autouse=True)
def database() -> Generator[None]:
    _reset_database()
    Base.metadata.create_all(engine)
    with TestingSession() as db:
        env = Environment(
            id="00000000-0000-0000-0000-000000000001",
            name="测试模拟环境",
            code="test-mock",
            enabled=True,
            environment_level=EnvironmentLevel.TEST,
        )
        disabled = Environment(
            id="00000000-0000-0000-0000-000000000002",
            name="停用模拟环境",
            code="disabled",
            enabled=False,
            environment_level=EnvironmentLevel.TEST,
        )
        host_ok = Host(
            id="10000000-0000-0000-0000-000000000001",
            name="mock-host-ok",
            environment=env,
            mock_behavior="success",
        )
        host_fail = Host(
            id="10000000-0000-0000-0000-000000000002",
            name="mock-host-fail",
            environment=env,
            mock_behavior="failure",
        )
        host_timeout = Host(
            id="10000000-0000-0000-0000-000000000003",
            name="mock-host-timeout",
            environment=env,
            mock_behavior="timeout",
        )
        service = Service(
            id="20000000-0000-0000-0000-000000000001",
            name="mock-service",
            service_type="application",
            environment=env,
        )
        other_service = Service(
            id="20000000-0000-0000-0000-000000000002",
            name="other-service",
            service_type="application",
            environment=env,
        )
        db.add_all([env, disabled, host_ok, host_fail, host_timeout, service, other_service])
        db.flush()
        db.add_all(
            [
                ServiceDeployment(service=service, host=host_ok),
                ServiceDeployment(service=service, host=host_fail),
                ServiceDeployment(service=service, host=host_timeout),
                ServiceDeployment(service=other_service, host=host_ok),
            ]
        )
        db.commit()
    yield
    _reset_database()


@pytest.fixture
def db() -> Generator[Session]:
    with TestingSession() as session:
        yield session


@pytest.fixture
def mock_write_settings() -> Settings:
    """Explicit opt-in used only by tests that exercise simulated writes."""
    return Settings(
        write_operations_enabled=True,
        production_operations_enabled=False,
        approval_required_for_write=False,
        _env_file=None,
    )


@pytest.fixture
def client() -> Generator[SyncASGIClient]:
    def override_db() -> Generator[Session]:
        with TestingSession() as session:
            yield session

    with TestingSession() as session:
        seed_default_admin(session, get_settings())
    app.dependency_overrides[get_db] = override_db
    # Avoid relying on Starlette TestClient's deprecated httpx bridge in the
    # constrained Python 3.13 runtime. Startup schema/seed behavior is explicit.
    test_client = SyncASGIClient()
    login = test_client.post(
        "/api/v1/auth/login", json={"username": "admin", "password": "admin123-test-only"}
    )
    assert login.status_code == 200
    test_client.headers["Authorization"] = f"Bearer {login.json()['access_token']}"
    yield test_client
    test_client.close()
    app.dependency_overrides.clear()
