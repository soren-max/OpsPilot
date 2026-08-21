from pathlib import Path

import pytest

from app.demo import DemoFinalState, load_scenario, render_demo, run_demo

SCENARIOS = Path(__file__).resolve().parents[3] / "demo/incidents"


@pytest.mark.parametrize("scenario_path", sorted(SCENARIOS.glob("*.yaml")))
def test_demo_scenario_is_valid_and_grounded(scenario_path: Path) -> None:
    scenario = load_scenario(scenario_path)
    assert scenario.expected_diagnosis.evidence_references


@pytest.mark.parametrize("scenario_path", sorted(SCENARIOS.glob("*.yaml")))
def test_demo_pipeline_is_deterministic_and_resumes_after_approval(
    scenario_path: Path,
) -> None:
    scenario = load_scenario(scenario_path)
    first = run_demo(scenario)
    second = run_demo(scenario)

    assert first == second
    assert first.final_state is DemoFinalState.SUCCEEDED
    assert first.approval_status == "APPROVED"
    assert first.verification_status == "SUCCEEDED"
    assert first.final_state.value == scenario.expected_workflow_state
    transcript = render_demo(scenario, first)
    assert "WAITING_APPROVAL" in transcript
    assert "Workflow Resumed" in transcript
