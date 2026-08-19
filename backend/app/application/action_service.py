from dataclasses import dataclass

from app.domain.actions.executor import ActionExecutor
from app.domain.actions.models import (
    ActionPreview,
    ActionRequest,
    ActionResult,
    RiskAssessment,
    VerificationResult,
)
from app.domain.actions.policy import ActionPolicyEngine


@dataclass(frozen=True)
class ActionExecutionOutcome:
    assessment: RiskAssessment
    preview: ActionPreview | None = None
    result: ActionResult | None = None
    verification: VerificationResult | None = None


class ActionService:
    """Application orchestration with explicit policy and executor dependencies."""

    def __init__(self, policy: ActionPolicyEngine, executor: ActionExecutor) -> None:
        self.policy = policy
        self.executor = executor

    async def preview(self, action: ActionRequest) -> ActionExecutionOutcome:
        assessment = self.policy.assess(action)
        if not assessment.allowed and not assessment.approval_required:
            return ActionExecutionOutcome(assessment=assessment)
        preview = await self.executor.preview(action)
        return ActionExecutionOutcome(assessment=assessment, preview=preview)

    async def execute(
        self, action: ActionRequest, *, approval_granted: bool = False
    ) -> ActionExecutionOutcome:
        assessment = self.policy.assess(
            action, approval_granted=approval_granted
        )
        if not assessment.allowed:
            return ActionExecutionOutcome(assessment=assessment)
        preview = await self.executor.preview(action)
        result = await self.executor.execute(action)
        verification = await self.executor.verify(action)
        return ActionExecutionOutcome(
            assessment=assessment,
            preview=preview,
            result=result,
            verification=verification,
        )
