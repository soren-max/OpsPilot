import json
from collections import defaultdict

from app.ai.models import (
    InvestigationPromptEvidence,
    InvestigationPromptInput,
    InvestigationPromptKnowledge,
)
from app.ai.prompts import PROMPT_NAME, PROMPT_VERSION
from app.domain.incidents.evidence import EvidenceType
from app.domain.incidents.memory import RetrievedKnowledge
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
# Ordered tuple rather than a set so packaging is deterministic across interpreter runs.
SAFE_METADATA_KEYS: tuple[str, ...] = (
    "entry_count",
    "metric_kind",
    "selected_values",
    "series_count",
    "status",
    "ticket_id",
)
MAX_SELECTED_VALUES = 10
MAX_HISTORICAL_ITEMS = 5


class EvidenceContextBuilder:
    """Packs bounded, typed, provenance-preserving evidence for the investigator.

    Current evidence is budgeted before historical context so history can never displace it,
    and every truncation is recorded on the packaged item rather than silently dropped.
    """

    def __init__(
        self,
        *,
        max_evidence: int = 20,
        max_summary_chars: int = 500,
        max_excerpt_chars: int = 1000,
        max_total_chars: int = 12_000,
        max_metadata_values: int = MAX_SELECTED_VALUES,
    ) -> None:
        self.max_evidence = max_evidence
        self.max_summary_chars = max_summary_chars
        self.max_excerpt_chars = max_excerpt_chars
        self.max_total_chars = max_total_chars
        self.max_metadata_values = max_metadata_values

    @classmethod
    def default_config(cls) -> dict[str, object]:
        """Serializable builder identity recorded with a frozen replay input."""

        defaults = cls()
        return {
            "schema": "evidence-context-1",
            "max_evidence": defaults.max_evidence,
            "max_summary_chars": defaults.max_summary_chars,
            "max_excerpt_chars": defaults.max_excerpt_chars,
            "max_total_chars": defaults.max_total_chars,
            "max_metadata_values": defaults.max_metadata_values,
        }

    def build(self, context: InvestigationContext) -> InvestigationPromptInput:
        packaged: list[InvestigationPromptEvidence] = []
        remaining = self.max_total_chars
        for item in self._select(context.evidence):
            candidate = self._package(item, remaining)
            if candidate is None:
                break
            remaining -= self._cost(candidate)
            packaged.append(candidate)
        return InvestigationPromptInput(
            incident_id=context.incident_id,
            service=context.service,
            environment=context.environment,
            evidence=tuple(packaged),
            historical_knowledge=self._package_history(
                context.historical_knowledge, max(remaining, 0)
            ),
            prompt_name=PROMPT_NAME,
            prompt_version=PROMPT_VERSION,
        )

    def _package(
        self, item: InvestigationEvidence, remaining: int
    ) -> InvestigationPromptEvidence | None:
        if remaining <= 0:
            return None
        summary = item.summary[: min(self.max_summary_chars, remaining)]
        if not summary:
            return None
        truncated = len(summary) < len(item.summary)
        remaining -= len(summary)
        raw_excerpt = item.excerpt or ""
        excerpt = raw_excerpt[: min(self.max_excerpt_chars, max(remaining, 0))]
        if len(excerpt) < len(raw_excerpt):
            truncated = True
        return InvestigationPromptEvidence(
            evidence_id=item.evidence_id,
            evidence_type=item.evidence_type,
            source=item.source,
            observed_at=item.observed_at,
            summary=summary,
            excerpt=excerpt or None,
            metadata=self._bounded_metadata(item.metadata),
            truncated=truncated,
            summarized=False,
        )

    def _package_history(
        self, knowledge: tuple[RetrievedKnowledge, ...], remaining: int
    ) -> tuple[InvestigationPromptKnowledge, ...]:
        packaged: list[InvestigationPromptKnowledge] = []
        for item in knowledge[:MAX_HISTORICAL_ITEMS]:
            cost = len(item.title) + len(item.root_cause)
            if cost > remaining:
                break
            remaining -= cost
            packaged.append(
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
            )
        return tuple(packaged)

    def _bounded_metadata(self, metadata: dict[str, JsonValue]) -> dict[str, JsonValue]:
        result: dict[str, JsonValue] = {}
        for key in SAFE_METADATA_KEYS:
            if key not in metadata:
                continue
            bounded = self._bounded_value(metadata[key])
            if bounded is not None:
                result[key] = bounded
        return result

    def _bounded_value(self, value: JsonValue) -> JsonValue:
        """Keep scalars and bounded scalar lists; drop nested structures entirely."""

        if value is None or isinstance(value, (bool, int, float)):
            return value
        if isinstance(value, str):
            return value[: self.max_summary_chars]
        if isinstance(value, list):
            items: list[JsonValue] = [
                self._bounded_value(entry)
                for entry in value
                if entry is None or isinstance(entry, (bool, int, float, str))
            ][: self.max_metadata_values]
            return items or None
        return None

    @staticmethod
    def _cost(item: InvestigationPromptEvidence) -> int:
        metadata = json.dumps(item.metadata, sort_keys=True, separators=(",", ":"))
        return len(item.summary) + len(item.excerpt or "") + len(metadata)

    def select_ids(self, evidence: tuple[InvestigationEvidence, ...]) -> tuple[str, ...]:
        """Expose the deterministic selection so frozen replay can record the real input."""

        return tuple(item.evidence_id for item in self._select(evidence))

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