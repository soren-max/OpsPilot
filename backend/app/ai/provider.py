from typing import Protocol

from app.ai.models import InvestigationPromptInput, StructuredReasoningResult


class StructuredReasoningProvider(Protocol):
    provider_name: str
    model_name: str

    async def generate_investigation(
        self, request: InvestigationPromptInput
    ) -> StructuredReasoningResult: ...
