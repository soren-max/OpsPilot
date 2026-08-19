from collections.abc import Callable
from typing import Any, TypeAlias, TypeVar

from langgraph.runtime import Runtime

from app.workflows.incident.context import IncidentWorkflowContext, IncidentWorkflowRuntime

T = TypeVar("T")
StateUpdate: TypeAlias = dict[str, Any]


def workflow_runtime(runtime: Runtime[IncidentWorkflowContext]) -> IncidentWorkflowRuntime:
    if runtime.context is None:
        raise RuntimeError("Incident workflow context is required")
    return runtime.context.runtime


def traced_node(
    runtime: Runtime[IncidentWorkflowContext], node: str, operation: Callable[[], T]
) -> T:
    capabilities = workflow_runtime(runtime)
    capabilities.node_started(node)
    result = operation()
    capabilities.node_completed(node, "SUCCEEDED")
    return result
