#!/usr/bin/env python3
"""Run the synthetic local demo three times and retain every outcome."""

from __future__ import annotations

import argparse
import json
import subprocess
import time
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "artifacts/demo-repeatability.json"

MARKERS = {
    "startup": "[1/10] Lab ready",
    "incident_created": "[3/10] Incident created",
    "evidence_collection": "[4/10] Evidence collected",
    "investigation": "[5/10] Diagnosis completed",
    "approval_requested": "[7/10] Approval required",
    "approval_resume": "[8/10] Workflow resumed",
    "execution": "[9/10] Remediation executed",
    "verification": "[10/10] Verification passed",
}


def run_once(index: int) -> dict[str, object]:
    started = time.perf_counter()
    observed: dict[str, float] = {}
    output: list[str] = []
    process = subprocess.Popen(
        ("make", "demo-local"),
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )
    assert process.stdout is not None
    for line in process.stdout:
        print(f"[demo {index}] {line}", end="")
        output.append(line)
        elapsed = time.perf_counter() - started
        for name, marker in MARKERS.items():
            if marker in line and name not in observed:
                observed[name] = elapsed
    return_code = process.wait()
    duration = time.perf_counter() - started
    transcript = "".join(output)
    success = return_code == 0 and "Final State: RESOLVED" in transcript

    def delta(end: str, start: str | None = None) -> float | None:
        if end not in observed or (start is not None and start not in observed):
            return None
        return round(observed[end] - (observed[start] if start else 0.0), 3)

    return {
        "run": index,
        "timestamp": datetime.now(UTC).isoformat(),
        "startup_success": "startup" in observed,
        "incident_created": "incident_created" in observed,
        "approval": "approval_resume" in observed,
        "execution": "execution" in observed,
        "verification": "verification" in observed,
        "final_state": "RESOLVED" if "Final State: RESOLVED" in transcript else "UNKNOWN",
        "duration_seconds": round(duration, 3),
        "phase_seconds": {
            "startup": delta("startup"),
            "evidence_collection": delta("evidence_collection", "incident_created"),
            "investigation": delta("investigation", "evidence_collection"),
            "approval_resume": delta("approval_resume", "approval_requested"),
            "execution": delta("execution", "approval_resume"),
            "verification": delta("verification", "execution"),
        },
        "result": "PASS" if success else "FAIL",
        "return_code": return_code,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run make demo-local repeatedly")
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    if args.runs < 1:
        raise SystemExit("--runs must be positive")
    runs = []
    try:
        for index in range(1, args.runs + 1):
            runs.append(run_once(index))
    finally:
        subprocess.run(("make", "demo-down"), cwd=ROOT, check=False, capture_output=True)
    successful = sum(item["result"] == "PASS" for item in runs)
    payload = {
        "schema_version": "1.0.0",
        "scenario": "service-down",
        "environment": "synthetic local Docker Lab",
        "sample_size": len(runs),
        "success_count": successful,
        "demo_success_rate": successful / len(runs) if runs else 0.0,
        "runs": runs,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"Demo repeatability: {successful}/{len(runs)}")
    if successful != len(runs):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
