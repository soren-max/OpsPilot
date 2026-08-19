from typing import Literal

ExecutionMode = Literal["mock", "integration-test", "production"]
ExecutorName = Literal[
    "mock",
    "dry_run",
    "local_services",
    "ansible_playbook",
    "script",
    "local_script",
    "ssh_script",
    "ansible",
]
