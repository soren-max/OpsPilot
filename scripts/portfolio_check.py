#!/usr/bin/env python3
"""Run the Portfolio v1.0 quality gate and print one compact scorecard."""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class Check:
    label: str
    command: tuple[str, ...]
    cwd: Path = ROOT


def execute(check: Check) -> bool:
    print(f"\n[{check.label}] {' '.join(check.command)}", flush=True)
    result = subprocess.run(check.command, cwd=check.cwd, check=False)
    return result.returncode == 0


def artifact_status(category: str) -> bool:
    path = ROOT / "artifacts/portfolio-benchmark.json"
    if not path.exists():
        return False
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload["categories"][category]["status"] == "PASS"


def demo_ready() -> bool:
    path = ROOT / "artifacts/demo-repeatability.json"
    if not path.exists():
        return False
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload.get("sample_size", 0) >= 3 and payload.get("demo_success_rate") == 1.0


def legacy_ready() -> bool:
    path = ROOT / "artifacts/legacy-compatibility.json"
    if not path.exists():
        return False
    return json.loads(path.read_text(encoding="utf-8")).get("result") == "PASS"


def main() -> None:
    checks = (
        Check(
            "Backend tests",
            ("uv", "run", "--project", "backend", "--no-sync", "pytest", "backend/tests"),
        ),
        Check(
            "Ruff",
            ("uv", "run", "--project", "backend", "--no-sync", "ruff", "check", "backend/app", "backend/tests"),
        ),
        Check(
            "Mypy strict",
            ("uv", "run", "--project", "backend", "--no-sync", "mypy", "backend/app"),
        ),
        Check("Frontend tests", ("npm", "test"), ROOT / "frontend"),
        Check("ESLint", ("npm", "run", "lint"), ROOT / "frontend"),
        Check("TypeScript", ("npm", "run", "typecheck"), ROOT / "frontend"),
        Check("Frontend build", ("npm", "run", "build"), ROOT / "frontend"),
        Check("Secret scan", ("python3", "scripts/check-secrets.py")),
        Check("Portfolio benchmark", ("make", "portfolio-benchmark")),
        Check("README metrics", ("python3", "scripts/check-portfolio-metrics.py")),
    )
    quality_results = {check.label: execute(check) for check in checks}
    rows = {
        "Architecture": quality_results["Backend tests"],
        "Unit Tests": quality_results["Backend tests"] and quality_results["Frontend tests"],
        "Incident E2E": demo_ready(),
        "Safety Eval": artifact_status("safety"),
        "Retrieval Eval": artifact_status("retrieval"),
        "MCP Contract": artifact_status("mcp_contract"),
        "Execution Recovery": artifact_status("execution_reliability"),
        "SSH Compatibility": artifact_status("legacy_compatibility") and legacy_ready(),
        "Demo Repeatability": demo_ready(),
        "Docs Consistency": quality_results["README metrics"],
    }
    passed = all(quality_results.values()) and all(rows.values())
    print("\nOpsPilot Portfolio v1.0\n")
    for label, result in rows.items():
        print(f"{label:<23} {'PASS' if result else 'FAIL'}")
    print(f"\nResult:\n\n{'PORTFOLIO READY' if passed else 'NOT READY'}")
    if not passed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
