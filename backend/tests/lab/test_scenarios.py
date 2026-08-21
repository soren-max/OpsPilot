from pathlib import Path

import pytest

from app.lab import LabScenario, load_scenario

SCENARIOS = Path(__file__).resolve().parents[3] / "lab/scenarios"


def test_all_four_typed_scenarios_are_present() -> None:
    scenarios = [load_scenario(path.stem) for path in sorted(SCENARIOS.glob("*.yml"))]
    assert {item.name for item in scenarios} == {
        "service-down",
        "high-error-rate",
        "dependency-unavailable",
        "prompt-injection-log",
    }
    assert all(item.cleanup == "reset" for item in scenarios)


def test_scenario_rejects_unknown_fields_and_arbitrary_injection() -> None:
    with pytest.raises(ValueError):
        LabScenario.model_validate(
            {
                "name": "service-down",
                "description": "invalid arbitrary action",
                "target": "web-01",
                "injection": "run-command",
                "expected_signals": ["SERVICE_UP_ZERO"],
                "expected_outcome": "restart_service",
                "cleanup": "reset",
                "command": "sh -c anything",
            }
        )


def test_prompt_injection_is_only_expected_evidence() -> None:
    scenario = load_scenario("prompt-injection-log")
    assert scenario.expected_outcome == "no_action_without_policy_and_approval"
    assert "UNTRUSTED_LOG_EVIDENCE" in scenario.expected_signals
