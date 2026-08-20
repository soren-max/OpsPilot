from collections.abc import Mapping
from pathlib import Path

from sqlalchemy.orm import Session

from app.adapters.ansible import AnsibleActionExecutor, AnsibleRunResult
from app.adapters.mock import MockActionExecutor
from app.application.incident_service import IncidentService
from app.application.workflow_service import WorkflowService
from app.core.config import Settings
from app.domain.actions.models import ActionRequest
from app.repositories.workflow_models import WorkflowRunStatus
from app.worker import build_action_service
from tests.workflows.test_incident_workflow import create_incident


class RecordingMockExecutor(MockActionExecutor):
    def __init__(self) -> None:
        super().__init__()
        self.executed: list[ActionRequest] = []

    async def execute(self, action: ActionRequest):  # type: ignore[no-untyped-def]
        self.executed.append(action)
        return await super().execute(action)


class RecordingAnsibleRunner:
    def __init__(self) -> None:
        self.calls: list[tuple[Path, str, Mapping[str, str | int]]] = []

    async def run(
        self,
        *,
        playbook: Path,
        target: str,
        variables: Mapping[str, str | int],
    ) -> AnsibleRunResult:
        self.calls.append((playbook, target, variables))
        return AnsibleRunResult(0, "ok", "")


class IndeterminateMockExecutor(RecordingMockExecutor):
    async def execute(self, action: ActionRequest):  # type: ignore[no-untyped-def]
        self.executed.append(action)
        raise ConnectionError("lost response after dispatch")


def mock_settings() -> Settings:
    return Settings(_env_file=None)


def ansible_settings(tmp_path: Path) -> Settings:
    return Settings(
        executor="ansible",
        ansible_inventory_path=str(tmp_path / "inventory.ini"),
        ansible_playbook_directory=str(tmp_path),
        execution_acknowledged=True,
        _env_file=None,
    )


def test_configured_mock_backend_is_used_by_workflow(db: Session) -> None:
    incident_id = create_incident(
        db, "read-only-check requested", target="mock-host-ok"
    )
    action_service = build_action_service(db, mock_settings())
    executor = RecordingMockExecutor()
    action_service.executor = executor
    service = WorkflowService(db, action_service=action_service)

    result = service.run(service.start(incident_id, "operator", "wired-mock-1").id)

    assert result.status is WorkflowRunStatus.SUCCEEDED
    assert len(executor.executed) == 1
    assert executor.executed[0].target == "mock-host-ok"
    assert result.state_references["workflow_id"] == result.id
    assert result.state_references["action_fingerprint"] == result.proposed_action_id
    assert result.state_references["execution_task_id"] == result.execution_task_id


def test_configured_ansible_backend_is_used_by_workflow(
    db: Session, tmp_path: Path
) -> None:
    incident_id = create_incident(
        db, "read-only-check requested", target="mock-host-ok"
    )
    runner = RecordingAnsibleRunner()
    action_service = build_action_service(
        db, ansible_settings(tmp_path), ansible_runner=runner
    )
    service = WorkflowService(db, action_service=action_service)

    result = service.run(service.start(incident_id, "operator", "wired-ansible-1").id)

    assert isinstance(action_service.executor, AnsibleActionExecutor)
    assert result.status is WorkflowRunStatus.SUCCEEDED
    assert [call[0].name for call in runner.calls] == [
        "service_status.yml",
        "service_status.yml",
    ]
    assert all(call[1] == "mock-host-ok" for call in runner.calls)


def test_worker_target_allowlist_blocks_workflow_adapter(db: Session) -> None:
    incident_id = create_incident(
        db, "read-only-check requested", target="disabled-target"
    )
    action_service = build_action_service(db, mock_settings())
    executor = RecordingMockExecutor()
    action_service.executor = executor
    service = WorkflowService(db, action_service=action_service)

    result = service.run(service.start(incident_id, "operator", "allowlist-1").id)

    assert result.status is WorkflowRunStatus.FAILED
    assert result.last_error == "POLICY_BLOCKED"
    assert executor.executed == []


def test_waiting_approval_never_invokes_mutating_adapter(db: Session) -> None:
    incident_id = create_incident(db, "service unavailable", target="mock-host-ok")
    action_service = build_action_service(db, mock_settings())
    executor = RecordingMockExecutor()
    action_service.executor = executor
    service = WorkflowService(db, action_service=action_service)

    result = service.run(service.start(incident_id, "operator", "approval-wiring-1").id)

    assert result.status is WorkflowRunStatus.WAITING
    assert result.execution_task_id is None
    assert executor.executed == []


def test_execute_retry_does_not_dispatch_same_action_twice(db: Session) -> None:
    incident_id = create_incident(
        db, "read-only-check requested", target="mock-host-ok"
    )
    action_service = build_action_service(db, mock_settings())
    executor = IndeterminateMockExecutor()
    action_service.executor = executor
    service = WorkflowService(db, action_service=action_service)

    result = service.run(service.start(incident_id, "operator", "dispatch-once-1").id)

    assert result.status is WorkflowRunStatus.FAILED
    assert len(executor.executed) == 1
    assert result.execution_task_id == result.proposed_action_id
    assert result.state_references == {
        "workflow_id": result.id,
        "action_fingerprint": result.proposed_action_id,
        "execution_task_id": result.execution_task_id,
        "execution_status": "STARTED",
    }
    assert IncidentService(db)._require(incident_id).status.value == "INVESTIGATING"
