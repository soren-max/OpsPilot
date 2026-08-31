# Evaluation

Status: **Portfolio v1.0 offline benchmark implemented; large-scale model evaluation is future work**

## Concept

Evaluation measures investigation quality, tool use, safety decisions, and recovery outcomes on
repeatable incidents.

## Where in OpsPilot

Current deterministic tests cover action safety. M3B adds reusable `InvestigationEvalCase`
fixtures, safety cases, and metrics (Evidence Precision, Evidence Recall, Action Accuracy,
Grounding Validity, Unsupported Action Rate). Portfolio v1.0 consolidates investigation, retrieval,
safety, reliability, MCP, compatibility, and demo evidence. Large-scale real-model and production
traffic evaluation remain explicit future work.

## Why

Agent quality cannot be inferred from a few successful demos.

## Trade-offs

Useful datasets and graders are expensive to maintain and can overfit implementation details.

## Failure Modes

Leaky test sets, weak graders, missing safety cases, nondeterminism, and outcome-only scoring.

## Interview Questions

- Which metrics separate diagnosis quality from action safety?
- How would you evaluate refusal and escalation behavior?
