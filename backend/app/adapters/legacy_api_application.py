from app.adapters.legacy_api import LegacyCompatibilityResult, LegacyRestartRequest
from app.adapters.mcp.application import WorkflowGovernedActionProposer
from app.adapters.mcp.contracts import RemediationToolInput


class LegacyApiCompatibilityAdapter:
    """Strangler adapter that can propose work but can never authorize or execute it."""

    def __init__(self, proposer: WorkflowGovernedActionProposer) -> None:
        self.proposer = proposer

    async def propose_restart(
        self, request: LegacyRestartRequest, *, actor: str
    ) -> LegacyCompatibilityResult:
        proposal = await self.proposer.propose(
            RemediationToolInput(
                incident_id=request.incident_id,
                action_type="restart_service",
                target=request.service,
                reason=request.reason,
                evidence_ids=request.evidence_ids,
            ),
            actor,
        )
        return LegacyCompatibilityResult(
            status="approval_required",
            risk_level=proposal.risk_level,
            approval_required=True,
            approval_id=proposal.approval_id,
            workflow_id=proposal.workflow_id,
        )
