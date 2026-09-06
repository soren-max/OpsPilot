"""Checkpoint the authoritative controller result, never caller-supplied gate flags."""

from collections.abc import Callable

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from app.workflows.change.state import ChangeWorkflowState

GRAPH_NAME = "gitops-change"
GRAPH_VERSION = "2"


def build_change_graph(
    *,
    advance: Callable[[str], str],
    checkpointer: BaseCheckpointSaver[str] | None = None,
) -> CompiledStateGraph[ChangeWorkflowState, None, ChangeWorkflowState, ChangeWorkflowState]:
    """Each invocation performs one bounded durable tick, then releases the worker.

    SQL approval/outbox/observation records authorize progress. Checkpoint state and
    invocation input cannot grant approval, fabricate merge, or skip verification.
    The next scheduled tick resumes by identity; it re-reads those durable records.
    """

    def advance_change(state: ChangeWorkflowState) -> ChangeWorkflowState:
        return {
            "change_id": state["change_id"],
            "status": advance(state["change_id"]),
            "current_node": "advance_change",
        }

    graph = StateGraph(ChangeWorkflowState)
    graph.add_node("advance_change", advance_change)
    graph.add_edge(START, "advance_change")
    graph.add_edge("advance_change", END)
    return graph.compile(checkpointer=checkpointer, name=GRAPH_NAME)
