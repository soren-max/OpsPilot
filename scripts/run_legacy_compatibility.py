#!/usr/bin/env python3
"""Execute and record the synthetic Ansible-over-SSH compatibility lifecycle."""

from __future__ import annotations

import json
import subprocess
import time
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "artifacts/legacy-compatibility.json"


def main() -> None:
    started = time.perf_counter()
    result = subprocess.run(
        ("make", "legacy-demo"), cwd=ROOT, check=False, capture_output=True, text=True
    )
    transcript = result.stdout + result.stderr
    print(transcript, end="")
    contract = subprocess.run(
        (
            "uv",
            "run",
            "--project",
            "backend",
            "--no-sync",
            "pytest",
            "-q",
            "backend/tests/deployment",
            "backend/tests/architecture/test_deployment_compatibility_boundaries.py",
        ),
        cwd=ROOT,
        check=False,
    )
    live_markers = (
        "Transport: Ansible over SSH",
        "Control: Fixed Script",
        "Policy: MEDIUM",
        "Approval: APPROVED",
        "Execution: SUCCEEDED",
        "Verification: PASSED",
        "Incident: RESOLVED",
    )
    live_passed = result.returncode == 0 and all(marker in transcript for marker in live_markers)
    passed = live_passed and contract.returncode == 0
    controls = {
        "ssh_transport": "PASS" if passed else "FAIL",
        "service_mapping": "PASS" if passed else "FAIL",
        "policy_boundary": "PASS" if passed else "FAIL",
        "hitl": "PASS" if passed else "FAIL",
        "fixed_script_control": "PASS" if passed else "FAIL",
        "command_injection": "BLOCKED" if passed else "FAIL",
        "verification": "PASS" if passed else "FAIL",
    }
    payload = {
        "schema_version": "1.0.0",
        "timestamp": datetime.now(UTC).isoformat(),
        "environment": "synthetic legacy Docker host",
        "duration_seconds": round(time.perf_counter() - started, 3),
        "live_lifecycle": "PASS" if live_passed else "FAIL",
        "contract_tests": "PASS" if contract.returncode == 0 else "FAIL",
        "controls": controls,
        "result": "PASS" if passed else "FAIL",
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    if not passed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
