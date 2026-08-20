from langgraph.runtime import Runtime

from app.workflows.incident.context import IncidentWorkflowContext
from app.workflows.incident.nodes.common import StateUpdate, traced_node, workflow_runtime
from app.workflows.incident.state import IncidentWorkflowState


def collect_context(
    state: IncidentWorkflowState, runtime: Runtime[IncidentWorkflowContext]
) -> StateUpdate:
    evidence_ids = traced_node(
        runtime,
        "collect_context",
        lambda: workflow_runtime(runtime).collect_context(list(state["evidence_ids"])),
    )
    return {"evidence_ids": evidence_ids, "current_node": "collect_context"}
