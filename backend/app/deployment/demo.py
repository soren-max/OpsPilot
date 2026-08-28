from __future__ import annotations

import urllib.request

from app.application.approval_service import ApprovalService
from app.application.incident_service import IncidentService
from app.application.workflow_service import WorkflowService
from app.core.config import get_settings
from app.db.session import SessionLocal
from app.domain.approvals import ApprovalActor
from app.domain.incidents.models import IncidentStatus, Severity
from app.execution.factory import build_execution_plane
from app.repositories.execution_models import ExecutionRecord
from app.repositories.workflow_models import WorkflowRunStatus
from app.schemas_incidents import IncidentCreate
from app.worker import (
    build_action_service,
    build_incident_capabilities,
    build_investigator,
)
from app.workflows.checkpoint import get_workflow_checkpointer

LEGACY_API = "http://legacy-host:8080"


def _post(path: str) -> None:
    request = urllib.request.Request(f"{LEGACY_API}{path}", method="POST")
    with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(
        request, timeout=10
    ) as response:
        if response.status != 200:
            raise RuntimeError("Synthetic legacy fault endpoint failed")


def main() -> None:
    settings = get_settings()
    get_workflow_checkpointer()
    _post("/fault/reset")
    _post("/fault/stop")
    print("Environment: Synthetic Legacy Test Server")
    print("Transport: Ansible over SSH")
    print("Control: Fixed Script")
    print("Fault: service-down")
    with SessionLocal() as db:
        action_service = build_action_service(db, settings)
        plane, dispatcher = build_execution_plane(db, settings, action_service)
        incident = IncidentService(db).create_incident(
            IncidentCreate(
                title="Synthetic demo-api is unavailable",
                summary="Health-only fallback detected a synthetic legacy service outage.",
                severity=Severity.HIGH,
                environment="test",
                service="demo-api",
                source="synthetic-legacy-lab",
                tags=["synthetic", "legacy", "ssh"],
            ),
            "legacy-demo",
        )
        workflows = WorkflowService(
            db,
            investigator=build_investigator(settings),
            action_service=action_service,
            capabilities=build_incident_capabilities(db, settings, action_service),
            execution_plane=plane,
            execution_dispatcher=dispatcher,
        )
        workflow = workflows.start(incident.id, "legacy-demo", "synthetic-service-down")
        waiting = workflows.run(workflow.id)
        assert waiting.status is WorkflowRunStatus.WAITING, waiting.last_error
        approval_id = waiting.state_references.get("approval_id")
        assert isinstance(approval_id, str)
        print("Action: restart_service")
        print("Policy: MEDIUM")
        ApprovalService(db).approve(
            approval_id,
            ApprovalActor(actor_id="legacy-operator", display_name="Legacy Demo Operator"),
            "Current health evidence confirms the synthetic service is unavailable.",
        )
        completed = workflows.resume(approval_id)
        execution = db.get(
            ExecutionRecord,
            str(completed.state_references.get("execution_id", "")),
        )
        execution_detail = (
            "execution record unavailable"
            if execution is None
            else (
                f"execution={execution.status.value}, "
                f"provider={execution.safe_provider_status}, "
                f"verification={execution.verification_status}"
            )
        )
        assert completed.status is WorkflowRunStatus.SUCCEEDED, (
            f"{completed.last_error}: {execution_detail}"
        )
        assert IncidentService(db)._require(incident.id).status is IncidentStatus.RESOLVED
        print("Approval: APPROVED")
        print("Execution: SUCCEEDED")
        print("Verification: PASSED")
        print("Incident: RESOLVED")
    _post("/fault/reset")


if __name__ == "__main__":
    main()
