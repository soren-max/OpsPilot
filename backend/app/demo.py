"""Offline, deterministic incident demo for portfolio walkthroughs."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
from enum import StrEnum
from pathlib import Path
from typing import Literal

import yaml  # type: ignore[import-untyped]
from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.adapters.mock import MockActionExecutor
from app.application.action_service import ActionService
from app.domain.actions.models import (
    ActionRequest,
    ActionType,
    ServiceActionParams,
    TargetEnvironment,
)
from app.domain.actions.policy import ActionPolicyEngine

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SCENARIO = REPOSITORY_ROOT / "demo/incidents/service-unavailable.yaml"


class DemoModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class DemoFinalState(StrEnum):
    SUCCEEDED = "SUCCEEDED"


class IncidentMetadata(DemoModel):
    id: str = Field(pattern=r"^demo-[a-z0-9-]+$")
    title: str
    severity: Literal["SEV1", "SEV2", "SEV3"]
    created_at: str


class DemoEvidence(DemoModel):
    id: str = Field(pattern=r"^ev-[a-z0-9-]+$")
    type: Literal["metric", "log", "health", "ticket"]
    source: str
    summary: str


class ExpectedDiagnosis(DemoModel):
    category: Literal[
        "service_unavailable", "high_error_rate", "insufficient_evidence"
    ]
    root_cause: str
    evidence_references: tuple[str, ...] = Field(min_length=1)


class ExpectedAction(DemoModel):
    type: ActionType
    target: str
    reason: str
    risk: Literal["read_only", "low", "medium", "high", "forbidden"]


class DemoScenario(DemoModel):
    schema_version: Literal[1]
    incident: IncidentMetadata
    service: str
    environment: TargetEnvironment
    initial_symptoms: tuple[str, ...] = Field(min_length=1)
    expected_evidence: tuple[DemoEvidence, ...] = Field(min_length=1)
    expected_diagnosis: ExpectedDiagnosis
    expected_action_proposal: ExpectedAction
    expected_workflow_state: Literal["SUCCEEDED"]

    @model_validator(mode="after")
    def diagnosis_references_existing_evidence(self) -> DemoScenario:
        evidence_ids = {item.id for item in self.expected_evidence}
        unknown = set(self.expected_diagnosis.evidence_references) - evidence_ids
        if unknown:
            raise ValueError(f"unknown evidence references: {sorted(unknown)}")
        return self


class DemoResult(DemoModel):
    incident_id: str
    diagnosis_category: str
    root_cause: str
    evidence_references: tuple[str, ...]
    action_type: ActionType
    risk: str
    approval_status: Literal["APPROVED"]
    checkpoint_id: str
    verification_status: Literal["SUCCEEDED"]
    final_state: DemoFinalState


def load_scenario(path: Path) -> DemoScenario:
    with path.open(encoding="utf-8") as stream:
        payload = yaml.safe_load(stream)
    return DemoScenario.model_validate(payload)


def investigate(scenario: DemoScenario) -> ExpectedDiagnosis:
    """Apply transparent fixture rules; evidence content is data, never instructions."""
    evidence = scenario.expected_evidence
    trusted = tuple(item for item in evidence if "untrusted data:" not in item.summary.lower())
    summaries = " ".join(item.summary.lower() for item in trusted)
    if "http_error_rate" in summaries and "degraded" in summaries:
        references = tuple(
            item.id for item in trusted if item.type in {"metric", "log", "health"}
        )
        return ExpectedDiagnosis(
            category="high_error_rate",
            root_cause=f"{scenario.service} worker pool is exhausted and timing out",
            evidence_references=references,
        )
    if "service_up = 0" in summaries and "unavailable" in summaries:
        return ExpectedDiagnosis(
            category="service_unavailable",
            root_cause=f"{scenario.service} is stopped after a failed service start",
            evidence_references=tuple(item.id for item in trusted),
        )
    return ExpectedDiagnosis(
        category="insufficient_evidence",
        root_cause="Available evidence does not establish an actionable root cause",
        evidence_references=tuple(item.id for item in trusted),
    )


def run_demo(scenario: DemoScenario) -> DemoResult:
    """Evaluate a fixture through the real deterministic action policy boundary."""
    diagnosis = investigate(scenario)
    if diagnosis != scenario.expected_diagnosis:
        raise ValueError("scenario diagnosis does not match deterministic investigation")
    proposal = scenario.expected_action_proposal
    request = ActionRequest(
        action_type=proposal.type,
        target=proposal.target,
        environment=scenario.environment,
        parameters=ServiceActionParams(service=scenario.service),
        reason=proposal.reason,
    )
    policy = ActionPolicyEngine(allowed_targets=frozenset({proposal.target}))
    assessment = policy.assess(request)
    if not assessment.approval_required or assessment.allowed:
        raise ValueError("demo must reach a blocked approval boundary")
    if assessment.risk_level.value != proposal.risk:
        raise ValueError("scenario risk does not match deterministic policy")

    # The offline demo models the durable boundary with a deterministic continuation ID.
    # Production uses LangGraph's PostgreSQL saver; the demo intentionally needs no service.
    checkpoint_id = hashlib.sha256(
        f"{scenario.incident.id}:{proposal.type.value}:{proposal.target}".encode()
    ).hexdigest()
    execution = asyncio.run(
        ActionService(policy, MockActionExecutor()).execute(request, approval_granted=True)
    )
    if execution.result is None or execution.verification is None:
        raise ValueError("approved demo action must execute and verify")
    result = DemoResult(
        incident_id=scenario.incident.id,
        diagnosis_category=diagnosis.category,
        root_cause=diagnosis.root_cause,
        evidence_references=diagnosis.evidence_references,
        action_type=proposal.type,
        risk=assessment.risk_level.value,
        approval_status="APPROVED",
        checkpoint_id=checkpoint_id,
        verification_status="SUCCEEDED" if execution.verification.verified else "FAILED",
        final_state=DemoFinalState.SUCCEEDED,
    )
    if result.final_state.value != scenario.expected_workflow_state:
        raise ValueError("scenario final state does not match pipeline result")
    return result


def render_demo(scenario: DemoScenario, result: DemoResult) -> str:
    evidence = "\n".join(
        f"  - {item.type.title():<6} [{item.id}] {item.summary}"
        for item in scenario.expected_evidence
    )
    refs = ", ".join(result.evidence_references)
    return f"""Incident Created
  {scenario.incident.id}: {scenario.incident.title}

Evidence Collected
{evidence}

Investigation Result
  category={result.diagnosis_category}

Diagnosis
  root_cause={result.root_cause}
  evidence_references={refs}

Action Proposal
  action={result.action_type.value}
  target={scenario.expected_action_proposal.target}

Risk Assessment
  risk={result.risk.upper()}
  approval_required=true

Approval Requested
  checkpoint={result.checkpoint_id[:16]}
  status=WAITING_APPROVAL

Human Decision
  actor=offline-demo-operator
  decision={result.approval_status}
  reason=fixture evidence supports bounded remediation

Workflow Resumed
  executor=mock
  verification={result.verification_status}

{result.final_state.value}"""


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("scenario", nargs="?", type=Path, default=DEFAULT_SCENARIO)
    args = parser.parse_args()
    scenario = load_scenario(args.scenario)
    print(render_demo(scenario, run_demo(scenario)))


if __name__ == "__main__":
    main()
