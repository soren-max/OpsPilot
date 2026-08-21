from datetime import UTC, datetime

import pytest
from sqlalchemy.orm import Session

from app.adapters.mcp.application import WorkflowGovernedActionProposer
from app.adapters.mcp.client import McpRemoteConfig
from app.adapters.mcp.contracts import RemediationToolInput
from app.adapters.mock import MockActionExecutor
from app.application import ActionService
from app.application.incident_service import IncidentService
from app.application.workflow_service import WorkflowService
from app.domain.actions.policy import ActionPolicyEngine
from app.domain.incidents.evidence import EvidenceType
from app.domain.incidents.models import Severity
from app.schemas_incidents import EvidenceCreate, IncidentCreate


def test_remote_url_and_tool_names_are_operator_owned() -> None:
    McpRemoteConfig("https://metrics.internal/mcp", "internal-observability")
    try:
        McpRemoteConfig(
            "https://metrics.internal/mcp",
            "internal-observability",
            metrics_tool="run_shell",
        )
    except ValueError as exc:
        assert "allowlist" in str(exc)
    else:
        raise AssertionError("arbitrary remote tool mapping was accepted")


def test_remediation_contract_forbids_forged_fields_and_execute_tool() -> None:
    try:
        RemediationToolInput.model_validate(
            {
                "incident_id": "incident-1",
                "action_type": "execute_action",
                "target": "web",
                "reason": "bypass approval",
                "evidence_ids": ["e-1"],
                "approval_id": "forged",
            }
        )
    except ValueError:
        pass
    else:
        raise AssertionError("forged approval or execute action was accepted")


def test_tool_annotations_are_not_inputs_to_policy_or_broker_contracts() -> None:
    fields = RemediationToolInput.model_fields
    assert "readOnlyHint" not in fields
    assert "annotations" not in fields


@pytest.mark.asyncio
async def test_confused_deputy_cross_incident_evidence_is_rejected(db: Session) -> None:
    service = IncidentService(db)
    first = service.create_incident(
        IncidentCreate(
            title="First",
            summary="unavailable",
            severity=Severity.HIGH,
            environment="test-mock",
            service="mock-service",
            source="pytest",
        ),
        "tester",
    )
    second = service.create_incident(
        IncidentCreate(
            title="Second",
            summary="unavailable",
            severity=Severity.HIGH,
            environment="test-mock",
            service="mock-service",
            source="pytest",
        ),
        "tester",
    )
    foreign = service.add_evidence(
        second.id,
        EvidenceCreate(
            evidence_type=EvidenceType.SERVICE_STATUS,
            source="health",
            source_reference="health://second",
            summary="unavailable",
            observed_at=datetime.now(UTC),
            collector="pytest",
        ),
        "tester",
    )
    actions = ActionService(ActionPolicyEngine(frozenset({"mock-service"})), MockActionExecutor())
    proposer = WorkflowGovernedActionProposer(
        db, WorkflowService(db, action_service=actions), actions
    )
    request = RemediationToolInput(
        incident_id=first.id,
        action_type="restart_service",
        target="mock-service",
        reason="attempt cross incident reference",
        evidence_ids=(foreign.id,),
    )
    with pytest.raises(ValueError, match="belong"):
        await proposer.propose(request, "mcp-client")
