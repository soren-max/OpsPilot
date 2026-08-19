import pytest

from app.core.config import Settings
from app.core.enums import OperationAction, TargetStatus
from app.executors.ansible import AnsibleExecutor, AnsibleExecutorConfig
from app.executors.base import ExecutionRequest
from app.executors.factory import build_executor
from app.queues import MemoryQueue, RedisQueue


def test_ansible_executor_remains_fixture_only() -> None:
    executor = AnsibleExecutor(AnsibleExecutorConfig())
    result = executor.execute(ExecutionRequest(OperationAction.STATUS, "demo", "service", "host"))
    assert result.status is TargetStatus.SUCCEEDED
    assert result.dry_run


def test_ansible_executor_real_command_path_is_hard_disabled() -> None:
    with pytest.raises(ValueError, match="Direct AnsibleExecutor execution is disabled"):
        AnsibleExecutor(AnsibleExecutorConfig(dry_run_only=False))
    with pytest.raises(NotImplementedError, match="ansible-playbook"):
        AnsibleExecutor(AnsibleExecutorConfig()).build_command(
            ExecutionRequest(OperationAction.STATUS, "demo", "service", "host")
        )


def test_executor_factory_supports_explicit_dry_run() -> None:
    result = build_executor(Settings(executor_type="dry_run")).execute(
        ExecutionRequest(OperationAction.STATUS, "demo", "service", "host")
    )
    assert result.dry_run


def test_memory_queue_is_deduplicated_and_redis_adapter_is_disconnected() -> None:
    queue = MemoryQueue()
    queue.enqueue("task-1")
    queue.enqueue("task-1")
    assert queue.dequeue() == "task-1"
    assert queue.dequeue() is None
    with pytest.raises(RuntimeError, match="not connected"):
        RedisQueue(None, "opspilot-ops-tasks").enqueue("task-1")
