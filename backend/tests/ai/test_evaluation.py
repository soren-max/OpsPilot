from pathlib import Path

from app.ai.evaluation import InvestigationEvalCase, evaluate_investigation
from app.ai.models import InvestigationModelOutput

CASES = Path(__file__).parents[1] / "fixtures" / "investigation_cases"


def output_for(case: InvestigationEvalCase) -> InvestigationModelOutput:
    return InvestigationModelOutput(
        statement="Bounded fixture result",
        root_cause=case.expected_root_cause_category,
        decision_summary="Auditable result from the supplied evidence.",
        confidence=0.9,
        evidence_ids=tuple(case.expected_evidence_ids),
        action_type=case.expected_action,
        insufficient_evidence=case.expected_insufficient_evidence,
        uncertainty="More observation is required" if case.expected_insufficient_evidence else None,
    )


def test_all_investigation_cases_score_expected_metrics() -> None:
    paths = sorted(CASES.glob("*.json"))
    assert {path.stem for path in paths} == {
        "service_down", "healthy_service", "high_error_rate", "redis_unavailable",
        "prompt_injection_log", "insufficient_evidence",
    }
    for path in paths:
        case = InvestigationEvalCase.model_validate_json(path.read_text(encoding="utf-8"))
        result = evaluate_investigation(case, output_for(case))
        assert result.evidence_precision == 1
        assert result.evidence_recall == 1
        assert result.action_accuracy == 1
        assert result.grounding_validity == 1
        assert result.unsupported_action_rate == 0
        assert result.insufficient_evidence_accuracy == 1
        assert result.root_cause_category_match == 1
