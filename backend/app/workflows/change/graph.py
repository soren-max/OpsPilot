from collections.abc import Callable

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from app.workflows.change.state import ChangeWorkflowState

GRAPH_NAME = "gitops-change"
GRAPH_VERSION = "1"


def _stage(name: str, status: str) -> Callable[[ChangeWorkflowState], ChangeWorkflowState]:
    def node(state: ChangeWorkflowState) -> ChangeWorkflowState:
        return {**state, "current_node": name, "status": status}

    return node


def _gate(flag: str, next_node: str) -> Callable[[ChangeWorkflowState], str]:
    def route(state: ChangeWorkflowState) -> str:
        return next_node if state.get(flag, False) else END

    return route


def _finalize(state: ChangeWorkflowState) -> ChangeWorkflowState:
    passed = state.get("verification_passed", False)
    return {
        **state,
        "current_node": "finalize",
        "status": "RESOLVED" if passed else "FAILED",
    }


def _add_stage(
    graph: StateGraph[
        ChangeWorkflowState,
        None,
        ChangeWorkflowState,
        ChangeWorkflowState,
    ],
    name: str,
    status: str,
) -> None:
    # LangGraph's overload accepts this callable at runtime, but its public typing
    # currently does not retain the TypedDict signature through a function factory.
    graph.add_node(name, _stage(name, status))  # type: ignore[call-overload]


def change_graph_builder() -> StateGraph[
    ChangeWorkflowState,
    None,
    ChangeWorkflowState,
    ChangeWorkflowState,
]:
    """Durable orchestration stops at external gates; workers never wait in-process."""

    graph = StateGraph(ChangeWorkflowState)
    for name, status in (
        ("prepare_change", "PROPOSED"),
        ("validate_change", "VALIDATED"),
        ("assess_change_policy", "POLICY_APPROVED"),
        ("request_approval", "WAITING_APPROVAL"),
        ("persist_change", "APPROVED"),
        ("queue_git_operation", "QUEUED"),
        ("create_pr", "PR_CREATED"),
        ("wait_external_review", "WAITING_REVIEW"),
        ("observe_merge", "APPROVED_FOR_MERGE"),
        ("observe_gitops", "RECONCILING"),
        ("verify", "VERIFIED"),
    ):
        _add_stage(graph, name, status)
    graph.add_node("finalize", _finalize)
    graph.add_edge(START, "prepare_change")
    graph.add_edge("prepare_change", "validate_change")
    graph.add_edge("validate_change", "assess_change_policy")
    graph.add_edge("assess_change_policy", "request_approval")
    graph.add_conditional_edges(
        "request_approval", _gate("approval_granted", "persist_change")
    )
    graph.add_edge("persist_change", "queue_git_operation")
    graph.add_edge("queue_git_operation", "create_pr")
    graph.add_edge("create_pr", "wait_external_review")
    graph.add_conditional_edges(
        "wait_external_review", _gate("review_approved", "observe_merge")
    )
    graph.add_conditional_edges("observe_merge", _gate("merged", "observe_gitops"))
    graph.add_conditional_edges(
        "observe_gitops",
        lambda state: (
            "verify"
            if state.get("gitops_synced", False) and state.get("gitops_healthy", False)
            else END
        ),
    )
    graph.add_edge("verify", "finalize")
    graph.add_edge("finalize", END)
    # END at a gate means durable waiting, not successful completion. Application
    # controllers persist real side effects and provide the observed flags on resume.
    return graph


def build_change_graph(
    checkpointer: BaseCheckpointSaver[str] | None = None,
) -> CompiledStateGraph[
    ChangeWorkflowState,
    None,
    ChangeWorkflowState,
    ChangeWorkflowState,
]:
    return change_graph_builder().compile(checkpointer=checkpointer, name=GRAPH_NAME)
