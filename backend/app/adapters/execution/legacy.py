from datetime import UTC, datetime

from app.domain.actions.executor import ActionExecutor
from app.domain.actions.models import (
    ActionRequest,
    ActionStatus,
    ActionType,
    RiskLevel,
    TargetEnvironment,
)
from app.domain.execution import (
    BackendType,
    ExecutionBackendDescriptor,
    ExecutionContext,
    ExecutionMode,
    ExecutionPreview,
    ExecutionStatus,
    ExecutionSubmission,
    ReconciliationResult,
)


class ActionExecutorBackend:
    """Compatibility adapter retaining Mock and Ansible ActionExecutor implementations."""

    def __init__(self, executor: ActionExecutor, backend_type: BackendType) -> None:
        if backend_type not in {BackendType.MOCK, BackendType.ANSIBLE}:
            raise ValueError("Legacy executor backend must be Mock or Ansible")
        self.executor = executor
        self.descriptor = ExecutionBackendDescriptor(
            backend_type=backend_type,
            supported_action_types=frozenset(ActionType),
            supported_modes=frozenset({ExecutionMode.REMEDIATE}),
            supported_environments=frozenset(TargetEnvironment),
            supports_async=False,
            supports_status=False,
            supports_cancel=False,
            supports_reconciliation=False,
            max_risk_level=RiskLevel.MEDIUM,
        )

    async def prepare(self, request: ActionRequest, context: ExecutionContext) -> ExecutionPreview:
        preview = await self.executor.preview(request)
        return ExecutionPreview(
            backend_type=self.descriptor.backend_type,
            profile_name=context.profile.name,
            operation=preview.operation,
            changes_state=preview.changes_state,
        )

    async def submit(
        self, request: ActionRequest, context: ExecutionContext
    ) -> ExecutionSubmission:
        result = await self.executor.execute(request)
        status = (
            ExecutionStatus.SUCCEEDED
            if result.status is ActionStatus.SUCCEEDED
            else ExecutionStatus.FAILED
        )
        return ExecutionSubmission(
            execution_id=context.execution_id,
            backend_type=self.descriptor.backend_type,
            backend_execution_id=context.execution_id,
            submitted_at=datetime.now(UTC),
            initial_status=status,
            safe_provider_status=result.status.value,
        )

    async def get_status(self, context: ExecutionContext) -> ReconciliationResult:
        return ReconciliationResult(
            execution_id=context.execution_id,
            status=ExecutionStatus.RECONCILIATION_REQUIRED,
            reconciled_at=datetime.now(UTC),
            safe_message="Synchronous backend has no remote status API",
        )

    async def reconcile(self, context: ExecutionContext) -> ReconciliationResult:
        return await self.get_status(context)
