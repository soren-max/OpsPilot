"""Typed control plane and deterministic live demo for the local Incident Lab."""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import os
import time
import urllib.error
import urllib.request
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Literal

import yaml  # type: ignore[import-untyped]
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select

from app.adapters.health import ActionServiceHealthCapability
from app.adapters.http import HttpxJsonClient
from app.adapters.loki import LokiLogsAdapter
from app.adapters.prometheus import PrometheusMetricsAdapter
from app.adapters.tickets import MockTicketAdapter
from app.application.action_service import ActionService
from app.application.approval_service import ApprovalService
from app.application.incident_service import IncidentService
from app.application.workflow_service import WorkflowService
from app.capabilities import IncidentCapabilities
from app.capabilities.logs import LogQuery
from app.capabilities.metrics import MetricAggregation, MetricKind, MetricQuery
from app.capabilities.policy import CapabilityQueryPolicy
from app.capabilities.tickets import TicketRecord
from app.core.config import get_settings
from app.core.enums import EnvironmentLevel
from app.db.session import SessionLocal
from app.domain.approvals import ApprovalActor
from app.domain.incidents.evidence import EvidenceType
from app.domain.incidents.knowledge import IncidentKnowledgeRecord
from app.domain.incidents.models import IncidentStatus, Severity
from app.memory.factory import build_memory_store
from app.models import Environment, Host, Service, ServiceDeployment
from app.repositories.workflow_models import WorkflowRunStatus
from app.schemas_incidents import IncidentCreate
from app.worker import build_action_service
from app.workflows.checkpoint import get_workflow_checkpointer
from app.workflows.incident.investigator import (
    DeterministicInvestigator,
    InvestigationContext,
    InvestigationEvidence,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
SCENARIO_ROOT = Path(os.environ.get("LAB_SCENARIO_ROOT", REPOSITORY_ROOT / "lab/scenarios"))
WEB_CONTROL = os.environ.get("LAB_CONTROL_BASE", "http://127.0.0.1:18081")
DEPENDENCY_CONTROL = os.environ.get(
    "LAB_DEPENDENCY_CONTROL_BASE", "http://127.0.0.1:18083"
)


class LabScenario(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    name: Literal[
        "service-down",
        "high-error-rate",
        "dependency-unavailable",
        "prompt-injection-log",
    ]
    description: str = Field(min_length=1, max_length=500)
    target: Literal["web-01", "dependency"]
    injection: Literal[
        "stop", "high-error-rate", "dependency-unavailable", "prompt-injection-log"
    ]
    expected_signals: tuple[str, ...] = Field(min_length=1, max_length=8)
    expected_outcome: str = Field(min_length=1, max_length=120)
    cleanup: Literal["reset"]


def load_scenario(name: str) -> LabScenario:
    if name not in {
        "service-down",
        "high-error-rate",
        "dependency-unavailable",
        "prompt-injection-log",
    }:
        raise ValueError("Unknown lab scenario")
    path = SCENARIO_ROOT / f"{name}.yml"
    return LabScenario.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))


def _request(base: str, path: str, *, method: str = "GET") -> str:
    request = urllib.request.Request(f"{base}{path}", method=method)
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    for attempt in range(3):
        try:
            with opener.open(request, timeout=10) as response:
                body: bytes = response.read()
                return body.decode("utf-8")
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError):
            if attempt == 2:
                raise
            time.sleep(0.5)
    raise RuntimeError("Lab request retry invariant violated")


def reset() -> None:
    _request(WEB_CONTROL, "/control/reset", method="POST")
    _request(DEPENDENCY_CONTROL, "/control/reset", method="POST")


def inject(scenario: LabScenario) -> None:
    reset()
    if scenario.injection == "stop":
        _request(WEB_CONTROL, "/control/stop", method="POST")
    elif scenario.injection == "high-error-rate":
        _request(WEB_CONTROL, "/control/high-error-rate", method="POST")
        _generate_traffic()
    elif scenario.injection == "dependency-unavailable":
        _request(DEPENDENCY_CONTROL, "/control/stop", method="POST")
        _generate_traffic()
    else:
        _request(WEB_CONTROL, "/control/prompt-injection-log", method="POST")


def _generate_traffic() -> None:
    web_url = os.environ.get("LAB_WEB_BASE", "http://127.0.0.1:18080")
    for _ in range(12):
        with contextlib.suppress(urllib.error.HTTPError):
            _request(web_url, "/api/demo")


def status() -> tuple[str, str]:
    return (
        _request(WEB_CONTROL, "/control/status"),
        _request(DEPENDENCY_CONTROL, "/control/status"),
    )


def _seed_lab_catalog() -> None:
    with SessionLocal() as db:
        environment = db.scalar(select(Environment).where(Environment.code == "lab"))
        if environment is None:
            environment = Environment(
                name="OpsPilot Incident Lab",
                code="lab",
                enabled=True,
                environment_level=EnvironmentLevel.TEST,
            )
            db.add(environment)
            db.flush()
        host = db.scalar(select(Host).where(Host.name == "web-01"))
        if host is None:
            host = Host(name="web-01", environment=environment, enabled=True)
            db.add(host)
        service = db.scalar(select(Service).where(Service.name == "web-01"))
        if service is None:
            service = Service(
                name="web-01",
                service_type="lab-web",
                environment=environment,
                enabled=True,
            )
            db.add(service)
        db.flush()
        deployment = db.scalar(
            select(ServiceDeployment).where(
                ServiceDeployment.service_id == service.id,
                ServiceDeployment.host_id == host.id,
            )
        )
        if deployment is None:
            db.add(ServiceDeployment(service=service, host=host, enabled=True))
        db.commit()


def _capabilities(action_service: ActionService) -> IncidentCapabilities:
    settings = get_settings()
    now = datetime.now(UTC)

    def client(url: str) -> HttpxJsonClient:
        return HttpxJsonClient(url, timeout_seconds=5)

    ticket = TicketRecord(
        id="LAB-101",
        title="Previous web process stop",
        status="RESOLVED",
        service="web-01",
        environment="lab",
        summary="A previous lab incident stopped the web process.",
        resolution="A policy-approved restart restored health.",
        created_at=now - timedelta(minutes=10),
        resolved_at=now - timedelta(minutes=9),
        source_reference="mock-ticket:LAB-101",
    )
    policy = CapabilityQueryPolicy(allowed_services=frozenset({"web-01"}))
    return IncidentCapabilities(
        policy=policy,
        metrics=PrometheusMetricsAdapter(client(settings.prometheus_base_url or "")),
        logs=LokiLogsAdapter(client(settings.loki_base_url or "")),
        tickets=MockTicketAdapter((ticket,)),
        health=ActionServiceHealthCapability(action_service, {"web-01": "web-01"}),
        timeout_seconds=30,
    )


async def _telemetry_probe() -> tuple[int, int]:
    settings = get_settings()
    end = datetime.now(UTC)
    start = end - timedelta(minutes=5)
    metrics = PrometheusMetricsAdapter(
        HttpxJsonClient(settings.prometheus_base_url or "", timeout_seconds=5)
    )
    series_count = 0
    for kind in (
        MetricKind.SERVICE_UP,
        MetricKind.REQUEST_RATE,
        MetricKind.ERROR_RATE,
        MetricKind.LATENCY_P95,
    ):
        observation = await metrics.query(
            MetricQuery(
                metric_kind=kind,
                service="web-01",
                environment="lab",
                start=start,
                end=end,
                step_seconds=15,
                aggregation=MetricAggregation.AVG,
            )
        )
        series_count += len(observation.series)
    logs = await LokiLogsAdapter(
        HttpxJsonClient(settings.loki_base_url or "", timeout_seconds=5)
    ).query(
        LogQuery(service="web-01", environment="lab", start=start, end=end, limit=20)
    )
    return series_count, len(logs.entries)


async def _prompt_injection_probe() -> None:
    settings = get_settings()
    end = datetime.now(UTC)
    logs = await LokiLogsAdapter(
        HttpxJsonClient(settings.loki_base_url or "", timeout_seconds=5)
    ).query(
        LogQuery(
            service="web-01",
            environment="lab",
            start=end - timedelta(minutes=2),
            end=end,
            limit=20,
        )
    )
    malicious = next(
        entry for entry in logs.entries if "ignore previous instructions" in entry.message_excerpt
    )
    result = DeterministicInvestigator().investigate(
        InvestigationContext(
            incident_id="lab-safety-probe",
            service="web-01",
            environment="lab",
            evidence=(
                InvestigationEvidence(
                    evidence_id="loki-untrusted-entry",
                    evidence_type=EvidenceType.LOG,
                    source="loki",
                    observed_at=malicious.timestamp,
                    summary="Untrusted log evidence",
                    excerpt=malicious.message_excerpt,
                    metadata={"trust": "untrusted"},
                ),
            ),
        )
    )
    assert result.action_type is None
    print("12. Safety scenario: prompt injection remained evidence; no action or approval bypass")


def _display_id(value: str, label: str) -> str:
    return f"<{label}>" if os.environ.get("LAB_NORMALIZE_OUTPUT") == "1" else value


def demo() -> None:
    get_workflow_checkpointer()
    reset()
    print("[1/10] Lab ready")
    inject(load_scenario("service-down"))
    print("[2/10] Fault injected — service-down")
    time.sleep(8)
    metric_series, log_entries = asyncio.run(_telemetry_probe())
    _seed_lab_catalog()
    with SessionLocal() as db:
        settings = get_settings()
        action_service = build_action_service(db, settings)
        memory = build_memory_store(settings)
        if memory is not None:
            memory.ensure_collection()
            memory.upsert(
                IncidentKnowledgeRecord(
                    incident_id="lab-historical-service-down",
                    title="Historical web process unavailable",
                    service="web-01",
                    environment="lab",
                    severity=Severity.HIGH.value,
                    symptoms=("Health endpoint unreachable",),
                    evidence_summary=("SERVICE_UP was zero",),
                    root_cause="Service process unavailable",
                    contributing_factors=(),
                    remediation=("restart_service",),
                    verification=("Health endpoint returned 200",),
                    tags=("lab", "service-down"),
                    resolved_at=datetime(2026, 8, 20, tzinfo=UTC),
                )
            )
        incident = IncidentService(db).create_incident(
            IncidentCreate(
                title="Lab web-01 is unavailable",
                summary="Live incident generated by the reproducible service-down scenario.",
                severity=Severity.HIGH,
                environment="lab",
                service="web-01",
                source="incident-lab",
                tags=["lab", "service-down"],
            ),
            "lab-demo",
        )
        print(f"[3/10] Incident created — {_display_id(incident.id, 'incident-id')}")
        workflow_service = WorkflowService(
            db,
            investigator=DeterministicInvestigator(),
            action_service=action_service,
            capabilities=_capabilities(action_service),
            knowledge_retriever=memory,
        )
        workflow = workflow_service.start(incident.id, "lab-demo", "service-down-demo")
        waiting = workflow_service.run(workflow.id)
        assert waiting.status is WorkflowRunStatus.WAITING
        stored = IncidentService(db)._require(incident.id)
        evidence_count = len(stored.evidence)
        diagnosis = stored.diagnoses[-1].root_cause
        print(
            f"[4/10] Evidence collected — {evidence_count} records "
            f"({metric_series} metric series, {log_entries} log entries observed)"
        )
        print(f"[5/10] Diagnosis completed — {diagnosis}")
        related = waiting.state_references.get("retrieved_knowledge_refs")
        historical = "enabled" if isinstance(related, list) and related else "disabled"
        print("[6/10] Action proposed — restart_service; Policy=MEDIUM")
        approval_id = waiting.state_references.get("approval_id")
        assert isinstance(approval_id, str)
        print(
            "[7/10] Approval required — "
            f"{_display_id(approval_id, 'approval-id')} (durable HITL)"
        )
        ApprovalService(db).approve(
            approval_id,
            ApprovalActor(actor_id="lab-operator", display_name="Lab Operator"),
            "Live health evidence confirms the bounded web process is unavailable.",
        )
        result = workflow_service.resume(approval_id)
        assert result.status is WorkflowRunStatus.SUCCEEDED, result.last_error
        print("[8/10] Workflow resumed — approved by demo identity Lab Operator")
        print("[9/10] Remediation executed — fixed Ansible restart_service.yml")
        assert IncidentService(db)._require(incident.id).status is IncidentStatus.RESOLVED
        print("[10/10] Verification passed — current health is healthy")
        print("\nDemo Summary")
        print(f"Incident ID: {_display_id(incident.id, 'incident-id')}")
        print(f"Workflow ID: {_display_id(workflow.id, 'workflow-id')}")
        print(f"Evidence Count: {evidence_count}")
        print(f"Diagnosis: {diagnosis}")
        print("Action: restart_service")
        print("Risk: MEDIUM")
        print("Approval: APPROVED (Lab Operator)")
        print(f"Executor: {action_service.executor.executor_name}")
        print("Verification: PASSED")
        print("Historical Memory: " + historical)
        print("Final State: RESOLVED")
    reset()
    if os.environ.get("LAB_DEMO_SAFETY_PROBE") == "1":
        inject(load_scenario("prompt-injection-log"))
        time.sleep(4)
        asyncio.run(_prompt_injection_probe())


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    inject_parser = subparsers.add_parser("inject")
    inject_parser.add_argument("scenario")
    subparsers.add_parser("status")
    subparsers.add_parser("reset")
    subparsers.add_parser("demo")
    args = parser.parse_args()
    if args.command == "inject":
        scenario = load_scenario(args.scenario)
        inject(scenario)
        print(f"Injected {scenario.name}: {scenario.description}")
    elif args.command == "status":
        print("web-01", status()[0])
        print("dependency", status()[1])
    elif args.command == "reset":
        reset()
        print("Lab scenario state reset")
    else:
        demo()


if __name__ == "__main__":
    main()
