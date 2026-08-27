import asyncio
from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from app.adapters.legacy_api import LegacyRestartRequest
from app.adapters.legacy_api_application import LegacyApiCompatibilityAdapter
from app.adapters.mcp.contracts import RemediationProposalResult
from app.adapters.tickets.legacy import LegacyTicketAdapter
from app.capabilities.tickets import TicketQuery


class FixtureClient:
    async def get_json(self, _path: str, *, params: object, headers: object = None) -> object:
        del params, headers
        now = datetime.now(UTC)
        return {
            "tickets": [
                {
                    "id": "SYN-1",
                    "title": "Synthetic ticket",
                    "status": "OPEN",
                    "service": "demo-api",
                    "environment": "test",
                    "summary": "Synthetic legacy system fixture",
                    "resolution": None,
                    "created_at": now.isoformat(),
                    "resolved_at": None,
                }
            ]
        }


class ApprovalOnlyProposer:
    def __init__(self) -> None:
        self.called = False

    async def propose(self, request: object, actor: str) -> RemediationProposalResult:
        del request, actor
        self.called = True
        return RemediationProposalResult(
            status="approval_required",
            risk_level="medium",
            approval_required=True,
            approval_id="approval-synthetic",
            workflow_id="workflow-synthetic",
        )


def test_legacy_ticket_contract_maps_to_ticket_capability() -> None:
    now = datetime.now(UTC)
    records = asyncio.run(
        LegacyTicketAdapter(FixtureClient()).search(  # type: ignore[arg-type]
            TicketQuery(
                service="demo-api",
                environment="test",
                start=now - timedelta(minutes=5),
                end=now + timedelta(minutes=5),
                limit=10,
            )
        )
    )
    assert records[0].source_reference == "legacy-ticket:SYN-1"


def test_legacy_api_adapter_returns_approval_and_cannot_execute() -> None:
    proposer = ApprovalOnlyProposer()
    adapter = LegacyApiCompatibilityAdapter(proposer)  # type: ignore[arg-type]
    result = asyncio.run(
        adapter.propose_restart(
            LegacyRestartRequest(
                incident_id="incident-synthetic",
                action="restart",
                service="demo-api",
                reason="Current evidence confirms synthetic unavailability.",
                evidence_ids=("evidence-synthetic",),
            ),
            actor="legacy-caller",
        )
    )
    assert proposer.called
    assert result.status == "approval_required"
    assert result.approval_required
    assert result.approval_id


@pytest.mark.parametrize("field", ["host", "ssh_user", "script_path", "command", "argv"])
def test_legacy_api_rejects_transport_and_command_fields(field: str) -> None:
    value = {
        "incident_id": "incident-synthetic",
        "action": "restart",
        "service": "demo-api",
        "reason": "Current evidence confirms synthetic unavailability.",
        "evidence_ids": ("evidence-synthetic",),
        field: "untrusted",
    }
    with pytest.raises(ValidationError):
        LegacyRestartRequest.model_validate(value)
