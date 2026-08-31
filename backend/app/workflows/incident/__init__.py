from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.workflows.incident.graph import build_incident_graph
    from app.workflows.incident.state import IncidentWorkflowState, WorkflowStatus

__all__ = ["IncidentWorkflowState", "WorkflowStatus", "build_incident_graph"]


def __getattr__(name: str) -> object:
    if name == "build_incident_graph":
        from app.workflows.incident.graph import build_incident_graph

        return build_incident_graph
    if name in {"IncidentWorkflowState", "WorkflowStatus"}:
        from app.workflows.incident.state import IncidentWorkflowState, WorkflowStatus

        return {
            "IncidentWorkflowState": IncidentWorkflowState,
            "WorkflowStatus": WorkflowStatus,
        }[name]
    raise AttributeError(name)
