from langgraph.runtime import Runtime

from app.workflows.incident.context import IncidentWorkflowContext
from app.workflows.incident.investigator import InvestigationResult
from app.workflows.incident.nodes.common import StateUpdate, traced_node, workflow_runtime
from app.workflows.incident.state import IncidentWorkflowState


def investigate(
    state: IncidentWorkflowState, runtime: Runtime[IncidentWorkflowContext]
) -> StateUpdate:
    capabilities = workflow_runtime(runtime)

    def investigate_and_record() -> tuple[InvestigationResult, str]:
        result = capabilities.investigate(state["retrieved_knowledge_ids"])
        return result, capabilities.record_hypothesis(result)

    result_value, hypothesis_id = traced_node(runtime, "investigate", investigate_and_record)
    result = result_value
    return {
        "hypothesis_ids": [hypothesis_id],
        "decision_summary": result.decision_summary,
        "proposed_action_type": result.action_type.value if result.action_type else None,
        "action_needed": result.action_type is not None,
        "investigation_statement": result.statement,
        "investigation_root_cause": result.root_cause,
        "investigation_confidence": result.confidence,
        "investigation_evidence_ids": list(result.evidence_ids),
        "insufficient_evidence": result.insufficient_evidence,
        "uncertainty": result.uncertainty,
        "current_node": "investigate",
    }
