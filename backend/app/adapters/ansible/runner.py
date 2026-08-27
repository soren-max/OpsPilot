from __future__ import annotations

import asyncio
import json
import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


@dataclass(frozen=True)
class AnsibleRunResult:
    exit_code: int
    stdout: str
    stderr: str


class AnsibleRunner(Protocol):
    async def run(
        self,
        *,
        playbook: Path,
        target: str,
        variables: Mapping[str, str | int],
    ) -> AnsibleRunResult: ...


class SubprocessAnsibleRunner:
    """Runs only application-owned playbooks and inventory without a shell."""

    def __init__(
        self,
        *,
        inventory: Path,
        playbook_root: Path,
        binary: Path = Path("/usr/bin/ansible-playbook"),
        timeout_seconds: int = 60,
        remote_user: str | None = None,
        private_key_file: Path | None = None,
        become_required: bool = False,
    ) -> None:
        self.inventory = inventory.resolve(strict=True)
        self.playbook_root = playbook_root.resolve(strict=True)
        self.binary = binary
        self.timeout_seconds = timeout_seconds
        self.remote_user = remote_user
        self.private_key_file = private_key_file
        self.become_required = become_required

    async def run(
        self,
        *,
        playbook: Path,
        target: str,
        variables: Mapping[str, str | int],
    ) -> AnsibleRunResult:
        resolved_playbook = playbook.resolve(strict=True)
        if resolved_playbook.parent != self.playbook_root:
            raise ValueError("Playbook must be an application-owned direct child")
        command = [
            str(self.binary),
            "-i",
            str(self.inventory),
            str(resolved_playbook),
            "--limit",
            target,
            "--extra-vars",
            json.dumps(dict(variables), separators=(",", ":"), sort_keys=True),
        ]
        if self.become_required:
            command.append("--become")
        process_environment = os.environ.copy()
        if self.remote_user:
            process_environment["ANSIBLE_REMOTE_USER"] = self.remote_user
        if self.private_key_file:
            process_environment["ANSIBLE_PRIVATE_KEY_FILE"] = str(self.private_key_file)
        process = await asyncio.create_subprocess_exec(
            *command,
            stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=process_environment,
        )
        try:
            stdout, stderr = await asyncio.wait_for(
                process.communicate(), timeout=self.timeout_seconds
            )
        except TimeoutError:
            process.kill()
            await process.wait()
            return AnsibleRunResult(124, "", "Ansible execution timed out")
        return AnsibleRunResult(
            process.returncode or 0,
            stdout.decode("utf-8", errors="replace"),
            stderr.decode("utf-8", errors="replace"),
        )
