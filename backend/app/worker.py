import signal
import time
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.adapters.ansible import AnsibleActionExecutor, SubprocessAnsibleRunner
from app.adapters.ansible.runner import AnsibleRunner
from app.adapters.mock import MockActionExecutor
from app.application import ActionService
from app.application.workflow_service import WorkflowService
from app.core.config import Settings, get_settings
from app.core.logging import configure_logging
from app.db.session import SessionLocal
from app.domain.actions.executor import ActionExecutor
from app.domain.actions.policy import ActionPolicyEngine
from app.models import Host
from app.services.worker import WorkerService

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
    targets = frozenset(db.scalars(select(Host.name).where(Host.enabled.is_(True))))
    return ActionService(ActionPolicyEngine(targets), executor)


def main() -> None:
    signal.signal(signal.SIGINT, stop_worker)
    signal.signal(signal.SIGTERM, stop_worker)
    settings = get_settings()
    configure_logging(settings.log_level, settings.log_file)
    while running:
        with SessionLocal() as db:
            action_service = build_action_service(db, settings)
            if WorkflowService(db, action_service=action_service).run_next():
                continue
            handled = WorkerService(db, action_service, settings).run_once()
        if not handled:
            time.sleep(settings.worker_poll_seconds)


if __name__ == "__main__":
    main()
