from typing import NotRequired, TypedDict


class ChangeWorkflowState(TypedDict):
    change_id: str
    incident_id: str
    workflow_id: str
    status: str
    current_node: str
    policy_result_ref: NotRequired[str]
    approval_id: NotRequired[str]
    pull_request_id: NotRequired[str]
    merged_revision: NotRequired[str]
    approval_granted: NotRequired[bool]
    review_approved: NotRequired[bool]
    merged: NotRequired[bool]
    gitops_synced: NotRequired[bool]
    gitops_healthy: NotRequired[bool]
    verification_passed: NotRequired[bool]
    error: NotRequired[str]
