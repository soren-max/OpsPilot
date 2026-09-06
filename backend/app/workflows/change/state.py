from typing import NotRequired, TypedDict


class ChangeWorkflowState(TypedDict):
    change_id: str
    status: NotRequired[str]
    current_node: NotRequired[str]
