from collections.abc import Callable
from typing import Any, TypeAlias, TypeVar

from langgraph.runtime import Runtime
from opentelemetry import trace

from app.workflows.incident.context import IncidentWorkflowContext, IncidentWorkflowRuntime

T = TypeVar("T")
StateUpdate: TypeAlias = dict[str, Any]
tracer = trace.get_tracer("opspilot.incident.workflow")

NODE_SPANS = {
    "load_incident": "incident.load",
    "collect_context": "evidence.collect",
    "retrieve_knowledge": "memory.retrieve",
    "investigate": "investigator.generate",
    "diagnose": "grounding.validate",
    "propose_action": "proposal.create",
    "assess_risk": "policy.evaluate",
    "approval_required": "approval.wait",
    "execute": "execution.dispatch",
    "verify": "verification.run",
    "finalize": "incident.finalize",
    "failure": "incident.fail",
}


def workflow_runtime(runtime: Runtime[IncidentWorkflowContext]) -> IncidentWorkflowRuntime:
    if runtime.context is None:
        raise RuntimeError("Incident workflow context is required")
    return runtime.context.runtime


def traced_node(
    runtime: Runtime[IncidentWorkflowContext], node: str, operation: Callable[[], T]
) -> T:
    capabilities = workflow_runtime(runtime)
    with tracer.start_as_current_span(NODE_SPANS.get(node, f"workflow.{node}")) as span:
        span.set_attribute("incident.id", capabilities.workflow.incident_id)
        span.set_attribute("workflow.run_id", capabilities.workflow.id)
        span.set_attribute("workflow.stage", node.upper())
        capabilities.node_started(node)
        try:
            result = operation()
        except Exception as exc:
            span.set_attribute("workflow.result", "FAILED")
            span.record_exception(exc, attributes={"exception.escaped": False})
            raise
        capabilities.node_completed(node, "SUCCEEDED")
        span.set_attribute("workflow.result", "SUCCEEDED")
        return result
