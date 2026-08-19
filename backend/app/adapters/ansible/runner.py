from __future__ import annotations

import asyncio
import json
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
    ) -> None:
        self.inventory = inventory.resolve(strict=True)
        self.playbook_root = playbook_root.resolve(strict=True)
        self.binary = binary
        self.timeout_seconds = timeout_seconds

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
        process = await asyncio.create_subprocess_exec(
            str(self.binary),
            "-i",
            str(self.inventory),
            str(resolved_playbook),
            "--limit",
            target,
            "--extra-vars",
            json.dumps(dict(variables), separators=(",", ":"), sort_keys=True),
            stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
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
