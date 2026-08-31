from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.application.action_service import ActionExecutionOutcome, ActionService
    from app.application.workflow_service import WorkflowService

__all__ = ["ActionExecutionOutcome", "ActionService", "WorkflowService"]


def __getattr__(name: str) -> object:
    if name in {"ActionExecutionOutcome", "ActionService"}:
        from app.application.action_service import ActionExecutionOutcome, ActionService

        return {
            "ActionExecutionOutcome": ActionExecutionOutcome,
            "ActionService": ActionService,
        }[name]
    if name == "WorkflowService":
        from app.application.workflow_service import WorkflowService

        return WorkflowService
    raise AttributeError(name)
