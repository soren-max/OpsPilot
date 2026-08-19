from typing import Protocol

from app.domain.actions.models import (
    ActionPreview,
    ActionRequest,
    ActionResult,
    VerificationResult,
)


class ActionExecutor(Protocol):
    executor_name: str

    async def preview(self, action: ActionRequest) -> ActionPreview: ...

    async def execute(self, action: ActionRequest) -> ActionResult: ...

    async def verify(self, action: ActionRequest) -> VerificationResult: ...
