from dataclasses import dataclass

from app.core.enums import OperationAction

WRITE_ACTIONS = {
    OperationAction.START,
    OperationAction.STOP,
    OperationAction.RESTART,
    OperationAction.DEPLOY,
}


@dataclass(frozen=True)
class PolicyRejection(Exception):
    code: str
    message: str
    field: str | None = None
