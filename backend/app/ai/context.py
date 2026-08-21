from collections import defaultdict

from app.ai.models import (
    InvestigationPromptEvidence,
    InvestigationPromptInput,
    InvestigationPromptKnowledge,
)
from app.ai.prompts import PROMPT_NAME, PROMPT_VERSION
from app.domain.incidents.evidence import EvidenceType
from app.domain.incidents.models import JsonValue
from app.workflows.incident.investigator import InvestigationContext, InvestigationEvidence

EVIDENCE_PRIORITY: dict[EvidenceType, int] = {
    EvidenceType.SERVICE_STATUS: 0,
    EvidenceType.ALERT: 1,
    EvidenceType.METRIC: 2,
    EvidenceType.LOG: 3,
    EvidenceType.TICKET: 4,
    EvidenceType.OPERATOR_NOTE: 5,
    EvidenceType.TOOL_RESULT: 6,
}
SAFE_METADATA_KEYS = frozenset(
    {"metric_kind", "series_count", "selected_values", "entry_count", "status", "ticket_id"}
)


class EvidenceContextBuilder:
    def __init__(
        self,
        *,
        max_evidence: int = 20,
        max_summary_chars: int = 500,
        max_excerpt_chars: int = 1000,
        max_total_chars: int = 12_000,
    ) -> None:
        self.max_evidence = max_evidence
        self.max_summary_chars = max_summary_chars
        self.max_excerpt_chars = max_excerpt_chars
        self.max_total_chars = max_total_chars

    def build(self, context: InvestigationContext) -> InvestigationPromptInput:
        selected = self._select(context.evidence)
        packaged: list[InvestigationPromptEvidence] = []
        remaining = self.max_total_chars
        for item in selected:
            summary = item.summary[: min(self.max_summary_chars, remaining)]
            remaining -= len(summary)
            if not summary or remaining <= 0:
                break
            excerpt = (item.excerpt or "")[: min(self.max_excerpt_chars, remaining)] or None
            remaining -= len(excerpt or "")
            metadata: dict[str, JsonValue] = {
                key: value
                for key, value in item.metadata.items()
                if key in SAFE_METADATA_KEYS and not isinstance(value, (dict, list))
            }
            packaged.append(
                InvestigationPromptEvidence(
                    evidence_id=item.evidence_id,
                    evidence_type=item.evidence_type,
                    source=item.source,
                    observed_at=item.observed_at,
                    summary=summary,
                    excerpt=excerpt,
                    metadata=metadata,
                )
            )
        return InvestigationPromptInput(
            incident_id=context.incident_id,
            service=context.service,
            environment=context.environment,
            evidence=tuple(packaged),
            historical_knowledge=tuple(
                InvestigationPromptKnowledge(
                    knowledge_id=item.knowledge_id,
                    incident_id=item.incident_id,
                    title=item.title[:200],
                    service=item.service,
                    environment=item.environment,
                    root_cause=item.root_cause[:2000],
                    remediation=item.remediation[:20],
                    verification=item.verification[:20],
                    source_reference=item.source_reference,
                )
                for item in context.historical_knowledge[:5]
            ),
            prompt_name=PROMPT_NAME,
            prompt_version=PROMPT_VERSION,
        )

    def _select(
        self, evidence: tuple[InvestigationEvidence, ...]
    ) -> tuple[InvestigationEvidence, ...]:
        ordered = sorted(
            evidence,
            key=lambda item: (
                EVIDENCE_PRIORITY[item.evidence_type],
                -item.observed_at.timestamp(),
                item.evidence_id,
            ),
        )
        by_source: dict[str, list[InvestigationEvidence]] = defaultdict(list)
        for item in ordered:
            by_source[item.source].append(item)
        selected: list[InvestigationEvidence] = []
        for source in sorted(
            by_source,
            key=lambda value: (
                EVIDENCE_PRIORITY[by_source[value][0].evidence_type], value
            ),
        ):
            selected.append(by_source[source].pop(0))
            if len(selected) == self.max_evidence:
                return tuple(selected)
        remaining = sorted(
            (item for items in by_source.values() for item in items),
            key=lambda item: (
                EVIDENCE_PRIORITY[item.evidence_type],
                -item.observed_at.timestamp(),
                item.evidence_id,
            ),
        )
        selected.extend(remaining[: self.max_evidence - len(selected)])
        return tuple(selected)
