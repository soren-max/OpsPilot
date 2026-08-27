from typing import Protocol

from app.domain.actions.models import ActionRequest
from app.domain.execution.models import (
    ExecutionBackendDescriptor,
    ExecutionContext,
    ExecutionPreview,
    ExecutionSubmission,
    ReconciliationResult,
)


class ExecutionBackend(Protocol):
    descriptor: ExecutionBackendDescriptor

    async def prepare(
        self, request: ActionRequest, context: ExecutionContext
    ) -> ExecutionPreview: ...

    async def submit(
        self, request: ActionRequest, context: ExecutionContext
    ) -> ExecutionSubmission: ...

    async def get_status(self, context: ExecutionContext) -> ReconciliationResult: ...

    async def reconcile(self, context: ExecutionContext) -> ReconciliationResult: ...
