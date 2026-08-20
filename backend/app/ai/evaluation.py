from pydantic import BaseModel, ConfigDict, Field

from app.ai.models import InvestigationModelOutput, InvestigationPromptEvidence
from app.domain.actions.models import ActionType


class InvestigationEvalCase(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    case_id: str
    incident_id: str
    service: str
    environment: str
    evidence: tuple[InvestigationPromptEvidence, ...]
    expected_evidence_ids: frozenset[str]
    expected_action: ActionType | None
    expected_insufficient_evidence: bool
    expected_root_cause_category: str


class InvestigationEvalResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    case_id: str
    evidence_precision: float = Field(ge=0, le=1)
    evidence_recall: float = Field(ge=0, le=1)
    action_accuracy: float = Field(ge=0, le=1)
    grounding_validity: float = Field(ge=0, le=1)
    unsupported_action_rate: float = Field(ge=0, le=1)
    insufficient_evidence_accuracy: float = Field(ge=0, le=1)
    root_cause_category_match: float = Field(ge=0, le=1)


def evaluate_investigation(
    case: InvestigationEvalCase, output: InvestigationModelOutput
) -> InvestigationEvalResult:
    predicted = set(output.evidence_ids)
    expected = set(case.expected_evidence_ids)
    true_positive = len(predicted & expected)
    precision = true_positive / len(predicted) if predicted else (1.0 if not expected else 0.0)
    recall = true_positive / len(expected) if expected else (1.0 if not predicted else 0.0)
    available = {item.evidence_id for item in case.evidence}
    grounded = predicted <= available and len(predicted) == len(output.evidence_ids)
    return InvestigationEvalResult(
        case_id=case.case_id,
        evidence_precision=precision,
        evidence_recall=recall,
        action_accuracy=float(output.action_type == case.expected_action),
        grounding_validity=float(grounded),
        unsupported_action_rate=0.0,
        insufficient_evidence_accuracy=float(
            output.insufficient_evidence == case.expected_insufficient_evidence
        ),
        root_cause_category_match=float(
            case.expected_root_cause_category.lower() in output.root_cause.lower()
        ),
    )
