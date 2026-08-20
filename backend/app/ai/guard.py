from dataclasses import dataclass

from app.ai.errors import LLMGroundingFailure, LLMPolicyViolation
from app.ai.models import InvestigationModelOutput, InvestigationPromptInput
from app.domain.actions.models import ActionType

MUTATING_ACTIONS = frozenset({ActionType.RESTART_SERVICE})


@dataclass(frozen=True)
class EvidenceGroundingValidator:
    def validate(
        self,
        output: InvestigationModelOutput,
        request: InvestigationPromptInput,
    ) -> None:
        available = {item.evidence_id for item in request.evidence}
        referenced = list(output.evidence_ids)
        if len(referenced) != len(set(referenced)):
            raise LLMGroundingFailure("Model returned duplicate evidence references")
        unknown = sorted(set(referenced) - available)
        if unknown:
            raise LLMGroundingFailure("Model referenced evidence outside the current incident")
        if not output.insufficient_evidence and not referenced:
            raise LLMGroundingFailure("A diagnosis requires supporting evidence")
        if output.action_type is not None and not referenced:
            raise LLMGroundingFailure("An action proposal requires supporting evidence")


@dataclass(frozen=True)
class InvestigationGuard:
    grounding: EvidenceGroundingValidator
    mutating_action_min_confidence: float = 0.8

    def validate(
        self,
        output: InvestigationModelOutput,
        request: InvestigationPromptInput,
    ) -> None:
        self.grounding.validate(output, request)
        if output.insufficient_evidence and output.action_type is not None:
            raise LLMPolicyViolation(
                "Insufficient evidence cannot produce an action proposal"
            )
        if (
            output.action_type in MUTATING_ACTIONS
            and output.confidence < self.mutating_action_min_confidence
        ):
            raise LLMPolicyViolation(
                "Mutating action confidence is below the configured threshold"
            )
