from pathlib import Path

import pytest

from app.demo import DemoFinalState, load_scenario, render_demo, run_demo

SCENARIOS = Path(__file__).resolve().parents[3] / "demo/incidents"


@pytest.mark.parametrize("scenario_path", sorted(SCENARIOS.glob("*.yaml")))
def test_demo_scenario_is_valid_and_grounded(scenario_path: Path) -> None:
    scenario = load_scenario(scenario_path)
    assert scenario.expected_diagnosis.evidence_references


@pytest.mark.parametrize("scenario_path", sorted(SCENARIOS.glob("*.yaml")))
def test_demo_pipeline_is_deterministic_and_stops_for_approval(
    scenario_path: Path,
) -> None:
    scenario = load_scenario(scenario_path)
    first = run_demo(scenario)
    second = run_demo(scenario)

    assert first == second
    assert first.final_state is DemoFinalState.WAITING_APPROVAL
    assert first.final_state.value == scenario.expected_workflow_state
    assert "WAITING_APPROVAL" in render_demo(scenario, first)
