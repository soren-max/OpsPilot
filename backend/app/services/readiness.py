from pathlib import Path
from typing import Any

from app.core.config import Settings


def execution_backend_readiness(settings: Settings) -> dict[str, Any]:
    """Report backend availability without transport implementation details."""
    backend = settings.selected_executor
    if backend == "mock":
        return {"backend": "mock", "available": True}
    if backend != "ansible":
        return {"backend": backend, "available": False}
    inventory = Path(settings.ansible_inventory_path or "")
    playbooks = Path(settings.ansible_playbook_directory or "")
    binary = Path(settings.ansible_binary_path or "/usr/bin/ansible-playbook")
    return {
        "backend": "ansible",
        "available": inventory.is_file() and playbooks.is_dir() and binary.is_file(),
    }
