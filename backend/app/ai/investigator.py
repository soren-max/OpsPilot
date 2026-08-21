import asyncio

from app.ai.context import EvidenceContextBuilder
from app.ai.errors import LLMFailure
from app.ai.guard import InvestigationGuard
from app.ai.models import InvestigationPromptInput, StructuredReasoningResult
from app.ai.provider import StructuredReasoningProvider
from app.workflows.incident.investigator import (
    InvestigationContext,
    InvestigationResult,
    InvestigatorMetadata,
)


class LLMIncidentInvestigator:
    mode = "llm"

    def __init__(
        self,
        provider: StructuredReasoningProvider,
        context_builder: EvidenceContextBuilder,
        guard: InvestigationGuard,
        *,
        max_retries: int = 1,
    ) -> None:
        self.provider = provider
        self.context_builder = context_builder
        self.guard = guard
        self.max_retries = max_retries

    @property
    def metadata(self) -> InvestigatorMetadata:
        return InvestigatorMetadata(
            mode=self.mode,
            provider=self.provider.provider_name,
            model=self.provider.model_name,
            prompt_version="1.0",
        )

    def investigate(self, context: InvestigationContext) -> InvestigationResult:
        request = self.context_builder.build(context)
        result = asyncio.run(self._generate(request))
        self.guard.validate(result.output, request)
        output = result.output
        return InvestigationResult(
            statement=output.statement,
            root_cause=output.root_cause,
            decision_summary=output.decision_summary,
            confidence=output.confidence,
            evidence_ids=output.evidence_ids,
            action_type=output.action_type,
            knowledge_refs=output.knowledge_refs,
            insufficient_evidence=output.insufficient_evidence,
            uncertainty=output.uncertainty,
            investigator_mode=self.mode,
            provider=result.provider,
            model=result.model,
            prompt_version=result.prompt_version,
            latency_ms=result.latency_ms,
            input_tokens=result.usage.input_tokens,
            output_tokens=result.usage.output_tokens,
        )

    async def _generate(
        self, request: InvestigationPromptInput
    ) -> StructuredReasoningResult:
        for attempt in range(self.max_retries + 1):
            try:
                return await self.provider.generate_investigation(request)
            except LLMFailure as exc:
                if not exc.retryable or attempt >= self.max_retries:
                    raise
                await asyncio.sleep(min(0.25 * (attempt + 1), 1.0))
        raise AssertionError("unreachable")
