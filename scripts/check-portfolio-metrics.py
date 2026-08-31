#!/usr/bin/env python3
"""Fail when README portfolio claims drift from the generated artifact."""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "README.md"
ARTIFACT = ROOT / "artifacts/portfolio-benchmark.json"
PATTERN = re.compile(r"<!-- portfolio-metric ([a-z0-9_]+)=([^ ]+) -->")


def rendered(value: object) -> str:
    if isinstance(value, float):
        return f"{value:.3f}"
    return str(value)


def main() -> None:
    payload = json.loads(ARTIFACT.read_text(encoding="utf-8"))
    categories = payload["categories"]
    expected = {
        "backend_tests": categories["quality_inventory"]["metrics"]["backend_tests_collected"],
        "frontend_tests": categories["quality_inventory"]["metrics"]["frontend_tests_declared"],
        "lab_scenarios": categories["quality_inventory"]["metrics"]["lab_scenarios"],
        "investigation_cases": categories["incident_investigation"]["metrics"]["case_count"],
        "retrieval_queries": categories["retrieval"]["metrics"]["query_count"],
        "safety_scenarios": categories["safety"]["metrics"]["scenario_count"],
        "safety_blocked_rate": categories["safety"]["metrics"]["blocked_rate"],
        "mcp_contract_rate": categories["mcp_contract"]["metrics"][
            "protocol_contract_pass_rate"
        ],
        "demo_sample_size": categories["demo_reproducibility"]["metrics"]["sample_size"],
        "demo_success_rate": categories["demo_reproducibility"]["metrics"][
            "demo_success_rate"
        ],
    }
    declared = dict(PATTERN.findall(README.read_text(encoding="utf-8")))
    problems = []
    for name, value in expected.items():
        actual = declared.get(name)
        wanted = rendered(value)
        if actual != wanted:
            problems.append(f"{name}: README={actual!r}, artifact={wanted!r}")
    if problems:
        raise SystemExit("Portfolio metric mismatch:\n" + "\n".join(problems))
    print(f"README portfolio metrics match {ARTIFACT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
