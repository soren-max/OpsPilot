from langgraph.runtime import Runtime

from app.domain.actions.models import ActionType
from app.workflows.incident.context import IncidentWorkflowContext
from app.workflows.incident.investigator import InvestigationResult
from app.workflows.incident.nodes.common import StateUpdate, traced_node, workflow_runtime
from app.workflows.incident.state import IncidentWorkflowState


def diagnose(
    state: IncidentWorkflowState, runtime: Runtime[IncidentWorkflowContext]
) -> StateUpdate:
    statement = state["investigation_statement"]
    root_cause = state["investigation_root_cause"]
    confidence = state["investigation_confidence"]
    if statement is None or root_cause is None or confidence is None:
        raise ValueError("Investigation result is incomplete")
    result = InvestigationResult(
        statement=statement,
        root_cause=root_cause,
        decision_summary=state["decision_summary"] or "Deterministic investigation completed",
        confidence=confidence,
        evidence_ids=tuple(state["investigation_evidence_ids"]),
        action_type=(
            ActionType(state["proposed_action_type"])
            if state["proposed_action_type"] is not None
            else None
        ),
    )
    diagnosis_id = traced_node(
        runtime, "diagnose", lambda: workflow_runtime(runtime).record_diagnosis(result)
    )
    return {"diagnosis_id": diagnosis_id, "current_node": "diagnose"}
