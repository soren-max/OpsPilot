import signal
import time
from datetime import timedelta
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.adapters.ansible import AnsibleActionExecutor, SubprocessAnsibleRunner
from app.adapters.ansible.runner import AnsibleRunner
from app.adapters.health import ActionServiceHealthCapability
from app.adapters.http import HttpxJsonClient
from app.adapters.loki import LokiLogsAdapter
from app.adapters.mock import MockActionExecutor
from app.adapters.prometheus import PrometheusMetricsAdapter
from app.adapters.tickets import MockTicketAdapter
from app.ai import EvidenceContextBuilder, EvidenceGroundingValidator, InvestigationGuard
from app.ai.adapters import OpenAIResponsesProvider
from app.ai.investigator import LLMIncidentInvestigator
from app.application import ActionService
from app.application.workflow_service import WorkflowService
from app.capabilities import IncidentCapabilities
from app.capabilities.policy import CapabilityQueryPolicy
from app.core.config import Settings, get_settings
from app.core.logging import configure_logging
from app.db.session import SessionLocal
from app.domain.actions.executor import ActionExecutor
from app.domain.actions.policy import ActionPolicyEngine
from app.models import Host, Service, ServiceDeployment
from app.services.worker import WorkerService
from app.workflows.checkpoint import get_workflow_checkpointer
from app.workflows.incident.investigator import DeterministicInvestigator, IncidentInvestigator

running = True


def stop_worker(_signum: int, _frame: object) -> None:
    global running
    running = False


def build_action_service(
    db: Session,
    settings: Settings,
    *,
    ansible_runner: AnsibleRunner | None = None,
) -> ActionService:
    """Build the single operator-configured execution boundary for a worker iteration."""
    executor: ActionExecutor = MockActionExecutor()
    if settings.selected_executor == "ansible":
        if not settings.ansible_inventory_path or not settings.ansible_playbook_directory:
            raise RuntimeError("Ansible backend requires operator-owned inventory and playbooks")
        playbook_root = Path(settings.ansible_playbook_directory)
        runner = ansible_runner or SubprocessAnsibleRunner(
            inventory=Path(settings.ansible_inventory_path),
            playbook_root=playbook_root,
            binary=Path(settings.ansible_binary_path or "/usr/bin/ansible-playbook"),
            timeout_seconds=settings.execution_timeout_seconds,
        )
        executor = AnsibleActionExecutor(
            runner=runner,
            playbook_root=playbook_root,
        )
    targets = frozenset(
        [
            *db.scalars(select(Host.name).where(Host.enabled.is_(True))),
            *db.scalars(select(Service.name).where(Service.enabled.is_(True))),
        ]
    )
    return ActionService(ActionPolicyEngine(targets), executor)


def build_incident_capabilities(
    db: Session, settings: Settings, action_service: ActionService
) -> IncidentCapabilities:
    """Compose bounded read-only investigation capabilities from operator settings."""
    services = frozenset(db.scalars(select(Service.name).where(Service.enabled.is_(True))))
    deployments = db.execute(
        select(Service.name, Host.name)
        .join(ServiceDeployment, ServiceDeployment.service_id == Service.id)
        .join(Host, Host.id == ServiceDeployment.host_id)
        .where(
            Service.enabled.is_(True),
            Host.enabled.is_(True),
            ServiceDeployment.enabled.is_(True),
        )
        .order_by(Service.name, Host.name)
    )
    targets_by_service: dict[str, str] = {}
    for service, target in deployments:
        targets_by_service.setdefault(service, target)
    policy = CapabilityQueryPolicy(
        allowed_services=services,
        max_time_range=timedelta(seconds=settings.capability_max_time_range_seconds),
        max_log_entries=settings.capability_max_log_entries,
        max_metric_series=settings.capability_max_metric_series,
        minimum_step_seconds=settings.capability_minimum_step_seconds,
    )

    def client(base_url: str, token: str | None) -> HttpxJsonClient:
        headers = {"Authorization": f"Bearer {token}"} if token else None
        return HttpxJsonClient(
            base_url,
            timeout_seconds=settings.capability_timeout_seconds,
            default_headers=headers,
        )

    prometheus_token = (
        settings.prometheus_auth_token.get_secret_value()
        if settings.prometheus_auth_token
        else None
    )
    loki_token = settings.loki_auth_token.get_secret_value() if settings.loki_auth_token else None
    metrics = (
        PrometheusMetricsAdapter(client(settings.prometheus_base_url, prometheus_token))
        if settings.prometheus_base_url
        else None
    )
    logs = (
        LokiLogsAdapter(
            client(settings.loki_base_url, loki_token),
            tenant=settings.loki_tenant,
            allowed_labels=policy.allowed_log_labels,
        )
        if settings.loki_base_url
        else None
    )
    return IncidentCapabilities(
        policy=policy,
        metrics=metrics,
        logs=logs,
        tickets=MockTicketAdapter(),
        health=ActionServiceHealthCapability(action_service, targets_by_service),
        timeout_seconds=settings.capability_timeout_seconds,
    )


def build_investigator(settings: Settings) -> IncidentInvestigator:
    if settings.llm_mode == "deterministic":
        return DeterministicInvestigator()
    if (
        settings.llm_provider != "openai"
        or settings.llm_model is None
        or settings.llm_api_key is None
    ):
        raise RuntimeError("LLM investigator configuration is incomplete")
    provider = OpenAIResponsesProvider(
        model=settings.llm_model,
        api_key=settings.llm_api_key.get_secret_value(),
        timeout_seconds=settings.llm_timeout_seconds,
    )
    return LLMIncidentInvestigator(
        provider,
        EvidenceContextBuilder(),
        InvestigationGuard(
            EvidenceGroundingValidator(),
            mutating_action_min_confidence=settings.llm_mutating_action_min_confidence,
        ),
        max_retries=settings.llm_max_retries,
    )


def main() -> None:
    signal.signal(signal.SIGINT, stop_worker)
    signal.signal(signal.SIGTERM, stop_worker)
    settings = get_settings()
    configure_logging(settings.log_level, settings.log_file)
    get_workflow_checkpointer()
    investigator = build_investigator(settings)
    while running:
        with SessionLocal() as db:
            action_service = build_action_service(db, settings)
            capabilities = build_incident_capabilities(db, settings, action_service)
            if WorkflowService(
                db,
                investigator=investigator,
                action_service=action_service,
                capabilities=capabilities,
            ).run_next():
                continue
            handled = WorkerService(db, action_service, settings).run_once()
        if not handled:
            time.sleep(settings.worker_poll_seconds)


if __name__ == "__main__":
    main()
