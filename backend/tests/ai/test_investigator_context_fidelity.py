from datetime import UTC, datetime

import pytest

from app.ai.context import MAX_SELECTED_VALUES, EvidenceContextBuilder
from app.ai.investigator import LLMIncidentInvestigator
from app.ai.models import (
    InvestigationModelOutput,
    StructuredReasoningResult,
)
from app.ai.prompts import PROMPT_NAME, PROMPT_VERSION, build_messages
from app.domain.actions.models import ActionType
from app.domain.incidents.evidence import EvidenceType
from app.domain.incidents.memory import RetrievedKnowledge
from app.workflows.incident.investigator import (
    InvestigationContext,
    InvestigationEvidence,
)

NOW = datetime(2026, 9, 21, tzinfo=UTC)


def metric(
    evidence_id: str, values: list[object], *, source: str = "prometheus"
) -> InvestigationEvidence:
    return InvestigationEvidence(
        evidence_id=evidence_id,
        evidence_type=EvidenceType.METRIC,
        source=source,
        observed_at=NOW,
        summary=f"Prometheus returned {len(values)} series",
        excerpt=None,
        metadata={
            "metric_kind": "service_up",
            "series_count": len(values),
            "selected_values": values,
        },
    )


def context(
    *evidence: InvestigationEvidence, historical: tuple[RetrievedKnowledge, ...] = ()
) -> InvestigationContext:
    return InvestigationContext(
        incident_id="incident-1",
        service="web",
        environment="production",
        evidence=tuple(evidence),
        historical_knowledge=historical,
    )


def knowledge(index: int) -> RetrievedKnowledge:
    return RetrievedKnowledge(
        knowledge_id=f"knowledge-{index}",
        incident_id=f"historical-{index}",
        title="Historical remediation",
        service="web",
        environment="production",
        root_cause="x" * 2000,
        remediation=("restart",),
        verification=("health",),
        retrieval_score=0.5,
        source_reference="/incidents/historical",
        resolved_at=NOW,
    )


@pytest.mark.parametrize("value", [0, 1])
def test_service_up_value_reaches_the_investigator_prompt(value: int) -> None:
    request = EvidenceContextBuilder().build(context(metric("e-1", [value])))

    assert request.evidence[0].metadata["selected_values"] == [value]
    rendered = build_messages(request)[1]["content"]
    assert f'"selected_values":[{value}]' in rendered


def test_selected_values_survive_the_llm_investigator_boundary() -> None:
    seen: dict[str, object] = {}

    class CapturingProvider:
        provider_name = "capture"
        model_name = "capture-model"

        async def generate_investigation(
            self, request: object
        ) -> StructuredReasoningResult:
            seen["request"] = request
            return StructuredReasoningResult(
                output=InvestigationModelOutput(
                    statement="The service is down.",
                    root_cause="Process unavailable",
                    decision_summary="The up metric is zero.",
                    confidence=0.9,
                    evidence_ids=("e-1",),
                    knowledge_refs=(),
                    action_type=ActionType.RESTART_SERVICE,
                    insufficient_evidence=False,
                    uncertainty=None,
                ),
                provider=self.provider_name,
                model=self.model_name,
                prompt_version=PROMPT_VERSION,
                latency_ms=5,
            )

    investigator = LLMIncidentInvestigator(
        CapturingProvider(),  # type: ignore[arg-type]
        EvidenceContextBuilder(),
        guard=type("G", (), {"validate": staticmethod(lambda output, request: None)})(),  # type: ignore[arg-type]
    )

    result = investigator.investigate(context(metric("e-1", [0])))

    captured = seen["request"]
    assert captured.evidence[0].metadata["selected_values"] == [0]  # type: ignore[attr-defined]
    assert result.input_evidence_ids == ("e-1",)


def test_selected_values_are_bounded_typed_and_deterministic() -> None:
    builder = EvidenceContextBuilder()
    values: list[object] = [*range(40)]
    item = metric("e-1", values)

    first = builder.build(context(item))
    second = builder.build(context(item))

    assert first == second
    bounded = first.evidence[0].metadata["selected_values"]
    assert isinstance(bounded, list)
    assert bounded == list(range(MAX_SELECTED_VALUES))


@pytest.mark.parametrize("value", [{"nested": "dict"}, [["nested", "list"]], object()])
def test_non_scalar_metadata_values_are_dropped(value: object) -> None:
    item = InvestigationEvidence(
        evidence_id="e-1",
        evidence_type=EvidenceType.METRIC,
        source="prometheus",
        observed_at=NOW,
        summary="metric",
        excerpt=None,
        metadata={"metric_kind": "service_up", "selected_values": [value]},
    )

    built = EvidenceContextBuilder().build(context(item))

    assert "selected_values" not in built.evidence[0].metadata


def test_long_log_truncates_with_provenance() -> None:
    item = InvestigationEvidence(
        evidence_id="e-1",
        evidence_type=EvidenceType.LOG,
        source="loki",
        observed_at=NOW,
        summary="log window",
        excerpt="x" * 5000,
        metadata={},
    )

    built = EvidenceContextBuilder().build(context(item))
    packaged = built.evidence[0]

    assert packaged.truncated is True
    assert len(packaged.excerpt or "") == 1000
    # No summarizer runs in this release, so the flag must never be asserted falsely.
    assert packaged.summarized is False
    assert packaged.evidence_id == "e-1"
    assert packaged.source == "loki"
    assert packaged.observed_at == NOW


def test_evidence_identity_is_preserved_when_nothing_is_truncated() -> None:
    item = InvestigationEvidence(
        evidence_id="e-1",
        evidence_type=EvidenceType.SERVICE_STATUS,
        source="service-health",
        observed_at=NOW,
        summary="Service web is unavailable.",
        excerpt=None,
        metadata={"status": "unavailable"},
    )

    packaged = EvidenceContextBuilder().build(context(item)).evidence[0]

    assert packaged.truncated is False
    assert packaged.evidence_id == "e-1"
    assert packaged.source == "service-health"
    assert packaged.observed_at == NOW
    assert packaged.metadata == {"status": "unavailable"}


def test_historical_context_cannot_displace_current_evidence() -> None:
    history = tuple(knowledge(index) for index in range(30))
    item = InvestigationEvidence(
        evidence_id="e-1",
        evidence_type=EvidenceType.SERVICE_STATUS,
        source="service-health",
        observed_at=NOW,
        summary="Service web is unavailable.",
        excerpt=None,
        metadata={},
    )

    builder = EvidenceContextBuilder(max_total_chars=1200)
    built = builder.build(context(item, historical=history))

    assert [entry.evidence_id for entry in built.evidence] == ["e-1"]
    assert built.evidence[0].summary == "Service web is unavailable."


def test_context_size_remains_bounded() -> None:
    evidence = tuple(
        InvestigationEvidence(
            evidence_id=f"e-{index}",
            evidence_type=EvidenceType.LOG,
            source=f"loki-{index}",
            observed_at=NOW,
            summary="s" * 900,
            excerpt="x" * 3000,
            metadata={"entry_count": index, "selected_values": list(range(50))},
        )
        for index in range(30)
    )

    built = EvidenceContextBuilder().build(context(*evidence, historical=(knowledge(0),)))
    size = sum(
        len(entry.summary) + len(entry.excerpt or "") for entry in built.evidence
    )

    assert size <= 12_000
    assert len(built.evidence) <= 20


def test_prompt_version_matches_the_investigator_metadata() -> None:
    class StubProvider:
        provider_name = "openai"
        model_name = "gpt-test"

    investigator = LLMIncidentInvestigator(
        StubProvider(),  # type: ignore[arg-type]
        EvidenceContextBuilder(),
        guard=type("G", (), {})(),  # type: ignore[arg-type]
    )

    assert investigator.metadata.prompt_version == PROMPT_VERSION

    built = EvidenceContextBuilder().build(context(metric("e-1", [0])))
    assert built.prompt_name == PROMPT_NAME
    assert built.prompt_version == PROMPT_VERSION