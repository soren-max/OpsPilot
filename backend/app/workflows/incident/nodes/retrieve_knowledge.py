from langgraph.runtime import Runtime

from app.workflows.incident.context import IncidentWorkflowContext
from app.workflows.incident.nodes.common import StateUpdate, traced_node, workflow_runtime
from app.workflows.incident.state import IncidentWorkflowState


def retrieve_knowledge(
    state: IncidentWorkflowState, runtime: Runtime[IncidentWorkflowContext]
) -> StateUpdate:
    del state
    knowledge_ids = traced_node(
        runtime, "retrieve_knowledge", workflow_runtime(runtime).retrieve_knowledge
    )
    return {
        "retrieved_knowledge_ids": knowledge_ids,
        "current_node": "retrieve_knowledge",
    }
