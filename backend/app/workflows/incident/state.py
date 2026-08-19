from enum import StrEnum
from typing import TypedDict


class WorkflowStatus(StrEnum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    WAITING_APPROVAL = "WAITING_APPROVAL"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class IncidentWorkflowState(TypedDict):
    incident_id: str
    workflow_id: str
    incident_version: int
    evidence_ids: list[str]
    hypothesis_ids: list[str]
    diagnosis_id: str | None
    proposed_action_id: str | None
    proposed_action_type: str | None
    risk_level: str | None
    execution_task_id: str | None
    verification_status: str | None
    workflow_status: str
    current_node: str | None
    decision_summary: str | None
    action_needed: bool
    approval_required: bool
    last_error: str | None
    retrieved_knowledge_ids: list[str]
    investigation_statement: str | None
    investigation_root_cause: str | None
    investigation_confidence: float | None
    investigation_evidence_ids: list[str]


def initial_state(incident_id: str, workflow_id: str) -> IncidentWorkflowState:
    return IncidentWorkflowState(
        incident_id=incident_id,
        workflow_id=workflow_id,
        incident_version=0,
        evidence_ids=[],
        hypothesis_ids=[],
        diagnosis_id=None,
        proposed_action_id=None,
        proposed_action_type=None,
        risk_level=None,
        execution_task_id=None,
        verification_status=None,
        workflow_status=WorkflowStatus.PENDING.value,
        current_node=None,
        decision_summary=None,
        action_needed=False,
        approval_required=False,
        last_error=None,
        retrieved_knowledge_ids=[],
        investigation_statement=None,
        investigation_root_cause=None,
        investigation_confidence=None,
        investigation_evidence_ids=[],
    )
