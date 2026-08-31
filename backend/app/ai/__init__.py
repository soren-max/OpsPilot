from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.ai.context import EvidenceContextBuilder
    from app.ai.guard import EvidenceGroundingValidator, InvestigationGuard
    from app.ai.investigator import LLMIncidentInvestigator
    from app.ai.provider import StructuredReasoningProvider

__all__ = [
    "EvidenceContextBuilder",
    "EvidenceGroundingValidator",
    "InvestigationGuard",
    "LLMIncidentInvestigator",
    "StructuredReasoningProvider",
]


def __getattr__(name: str) -> object:
    if name == "EvidenceContextBuilder":
        from app.ai.context import EvidenceContextBuilder

        return EvidenceContextBuilder
    if name in {"EvidenceGroundingValidator", "InvestigationGuard"}:
        from app.ai.guard import EvidenceGroundingValidator, InvestigationGuard

        return {
            "EvidenceGroundingValidator": EvidenceGroundingValidator,
            "InvestigationGuard": InvestigationGuard,
        }[name]
    if name == "LLMIncidentInvestigator":
        from app.ai.investigator import LLMIncidentInvestigator

        return LLMIncidentInvestigator
    if name == "StructuredReasoningProvider":
        from app.ai.provider import StructuredReasoningProvider

        return StructuredReasoningProvider
    raise AttributeError(name)
