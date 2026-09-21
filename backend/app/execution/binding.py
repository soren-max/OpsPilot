from __future__ import annotations

from app.domain.actions.models import ActionRequest
from app.services.reliability import request_fingerprint

# Bump when the bound field set changes so recorded approvals remain interpretable.
PROPOSAL_VERSION = "1"
DISPATCH_EXECUTION_PLANE = "execution_plane"
DISPATCH_ACTION_SERVICE = "action_service"


def execution_binding(
    request: ActionRequest,
    *,
    dispatch: str,
    backend_type: str | None = None,
    profile_name: str | None = None,
    profile_config: dict[str, object] | None = None,
) -> dict[str, object]:
    """Execution-relevant snapshot of a proposed action.

    Only fields that can change the external side effect are bound. Free-text such as
    ``request.reason`` and investigator prose are deliberately excluded, so re-wording an
    explanation never invalidates an approval while retargeting one always does.
    """

    return {
        "proposal_version": PROPOSAL_VERSION,
        "dispatch": dispatch,
        "action": {
            "action_type": request.action_type.value,
            "target": request.target,
            "environment": request.environment.value,
            "parameters": request.parameters.model_dump(mode="json"),
        },
        "backend_type": backend_type,
        "profile_name": profile_name,
        "profile_config": profile_config or {},
    }


def binding_digest(binding: dict[str, object]) -> str:
    """Deterministic digest: key order in the caller's dict cannot change the result."""

    return request_fingerprint(binding)