"""Read-only prerequisite and live readiness checks for the local portfolio demo."""

from __future__ import annotations

import argparse
import shutil
import socket
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMPOSE = ("docker", "compose", "-f", str(ROOT / "lab/docker-compose.yml"))
PORTS = {
    "Postgres": 55433,
    "Lab service": 18080,
    "Lab control": 18081,
    "Lab replica": 18082,
    "Dependency": 18083,
    "Prometheus": 19090,
    "Loki": 13100,
}


class Doctor:
    def __init__(self) -> None:
        self.failures = 0

    def check(self, name: str, ok: bool, detail: str) -> None:
        print(f"{'PASS' if ok else 'FAIL':4}  {name:<18} {detail}")
        if not ok:
            self.failures += 1


def command_ok(command: tuple[str, ...]) -> bool:
    try:
        return subprocess.run(
            command,
            cwd=ROOT,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=20,
            check=False,
        ).returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def port_available(port: int) -> bool:
    with socket.socket() as probe:
        probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            probe.bind(("127.0.0.1", port))
        except OSError:
            return False
    return True


def url_ready(url: str) -> bool:
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(url, timeout=3) as response:
            status = int(response.status)
            return 200 <= status < 400
    except (urllib.error.URLError, TimeoutError):
        return False


def prerequisites(doctor: Doctor) -> None:
    doctor.check("Docker CLI", shutil.which("docker") is not None, "docker is installed")
    docker_ready = command_ok(("docker", "info"))
    doctor.check("Docker daemon", docker_ready, "daemon is reachable")
    compose_ready = command_ok(("docker", "compose", "version"))
    doctor.check("Compose", compose_ready, "Docker Compose v2 is available")
    config_ready = docker_ready and compose_ready and command_ok((*COMPOSE, "config", "--quiet"))
    doctor.check("Compose config", config_ready, "lab compose file is valid")
    doctor.check(
        "Ansible assets",
        (ROOT / "lab/ansible/inventory.ini").is_file()
        and (ROOT / "lab/ansible/playbooks/restart_service.yml").is_file(),
        "fixed inventory and playbook are present",
    )
    doctor.check("Backend", (ROOT / "backend/app/lab.py").is_file(), "Lab runner is present")
    for name, port in PORTS.items():
        doctor.check(f"Port {port}", port_available(port), f"available for {name}")


def live_checks() -> dict[str, bool]:
    return {
        "Postgres": command_ok(
            (*COMPOSE, "exec", "-T", "postgres", "pg_isready", "-U", "opspilot")
        ),
        "Prometheus": url_ready("http://127.0.0.1:19090/-/ready"),
        "Loki": url_ready("http://127.0.0.1:13100/ready"),
        "Lab service": url_ready("http://127.0.0.1:18081/control/status"),
        "Dependency": url_ready("http://127.0.0.1:18083/control/status"),
    }


def live(doctor: Doctor) -> None:
    deadline = time.monotonic() + 60
    checks = live_checks()
    while not all(checks.values()) and time.monotonic() < deadline:
        time.sleep(2)
        checks = live_checks()
    for name, ready in checks.items():
        doctor.check(
            name,
            ready,
            "ready" if ready else "not ready after 60s; run make demo-reset",
        )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true")
    args = parser.parse_args()
    doctor = Doctor()
    print("OpsPilot Demo Doctor")
    live(doctor) if args.live else prerequisites(doctor)
    if doctor.failures:
        print(f"\nFAIL: {doctor.failures} check(s) failed. Fix them, then run make demo-doctor.")
        raise SystemExit(1)
    print("\nPASS: local demo environment is ready.")


if __name__ == "__main__":
    main()
