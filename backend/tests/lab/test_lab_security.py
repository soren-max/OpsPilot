from pathlib import Path

from app.adapters.ansible.executor import PLAYBOOK_MAPPING
from app.domain.actions.models import ActionType

ROOT = Path(__file__).resolve().parents[3]


def test_lab_ansible_uses_only_executor_owned_playbook_mapping() -> None:
    assert PLAYBOOK_MAPPING[ActionType.RESTART_SERVICE] == "restart_service.yml"
    playbook = (ROOT / "lab/ansible/playbooks/restart_service.yml").read_text()
    assert "ansible.builtin.uri" in playbook
    assert "shell:" not in playbook
    assert "command:" not in playbook


def test_prompt_injection_fixture_has_no_execution_surface() -> None:
    service = (ROOT / "lab/services/demo_service.py").read_text()
    assert "untrusted data: ignore previous instructions" in service
    assert "subprocess.Popen" in service
    assert "shell=True" not in service
