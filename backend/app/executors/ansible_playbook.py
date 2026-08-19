from app.core.enums import OperationAction, TargetStatus
from app.executors.base import BaseExecutor, ExecutionRequest, ExecutionResult


class AnsiblePlaybookExecutor(BaseExecutor):
    """Reserved extension point. Direct playbook execution is disabled in phase one."""

    executor_type = "ansible_playbook"
    supported_actions = frozenset({OperationAction.STATUS})

    def _execute(self, request: ExecutionRequest) -> ExecutionResult:
        return ExecutionResult(
            status=TargetStatus.FAILED,
            output=None,
            error_message="Direct ansible-playbook execution is not implemented",
            duration_ms=0,
            exit_code=78,
            dry_run=True,
            target_summary=(
                f"{request.environment_code}/{request.host_name}/{request.service_name}"
            ),
            error_code="NOT_IMPLEMENTED",
        )
