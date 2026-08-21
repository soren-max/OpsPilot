from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import RetryPolicy

from app.workflows.incident.context import IncidentWorkflowContext
from app.workflows.incident.errors import WorkflowInfrastructureFailure
from app.workflows.incident.nodes import (
    approval_required,
    assess_risk,
    collect_context,
    diagnose,
    execute,
    failure,
    finalize,
    investigate,
    load_incident,
    propose_action,
    retrieve_knowledge,
    verify,
)
from app.workflows.incident.routing import (
    route_after_approval,
    route_after_diagnosis,
    route_after_risk,
    route_after_verify,
)
from app.workflows.incident.state import IncidentWorkflowState

GRAPH_NAME = "incident-remediation"
GRAPH_VERSION = "2"


def incident_graph_builder() -> StateGraph[
    IncidentWorkflowState,
    IncidentWorkflowContext,
    IncidentWorkflowState,
    IncidentWorkflowState,
]:
    graph = StateGraph(IncidentWorkflowState, context_schema=IncidentWorkflowContext)
    graph.add_node("load_incident", load_incident)
    graph.add_node("collect_context", collect_context)
    graph.add_node("retrieve_knowledge", retrieve_knowledge)
    graph.add_node("investigate", investigate)
    graph.add_node("diagnose", diagnose)
    graph.add_node("propose_action", propose_action)
    graph.add_node("assess_risk", assess_risk)
    graph.add_node("approval_required", approval_required)
    graph.add_node(
        "execute",
        execute,
        retry_policy=RetryPolicy(
            max_attempts=3,
            jitter=False,
            retry_on=WorkflowInfrastructureFailure,
        ),
    )
    graph.add_node("verify", verify)
    graph.add_node("failure", failure)
    graph.add_node("finalize", finalize)
    graph.add_edge(START, "load_incident")
    graph.add_edge("load_incident", "collect_context")
    graph.add_edge("collect_context", "retrieve_knowledge")
    graph.add_edge("retrieve_knowledge", "investigate")
    graph.add_edge("investigate", "diagnose")
    graph.add_conditional_edges("diagnose", route_after_diagnosis)
    graph.add_edge("propose_action", "assess_risk")
    graph.add_conditional_edges("assess_risk", route_after_risk)
    graph.add_conditional_edges("approval_required", route_after_approval)
    graph.add_edge("execute", "verify")
    graph.add_conditional_edges("verify", route_after_verify)
    graph.add_edge("failure", END)
    graph.add_edge("finalize", END)
    return graph


def build_incident_graph(
    checkpointer: BaseCheckpointSaver[str] | None = None,
) -> CompiledStateGraph[
    IncidentWorkflowState,
    IncidentWorkflowContext,
    IncidentWorkflowState,
    IncidentWorkflowState,
]:
    return incident_graph_builder().compile(checkpointer=checkpointer, name=GRAPH_NAME)
