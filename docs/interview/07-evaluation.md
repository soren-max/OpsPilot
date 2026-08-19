# Evaluation

Status: **Planned**

## Concept

Evaluation measures investigation quality, tool use, safety decisions, and recovery outcomes on
repeatable incidents.

## Where in OpsPilot

Current deterministic tests cover action safety. Incident and model evaluation are planned.

## Why

Agent quality cannot be inferred from a few successful demos.

## Trade-offs

Useful datasets and graders are expensive to maintain and can overfit implementation details.

## Failure Modes

Leaky test sets, weak graders, missing safety cases, nondeterminism, and outcome-only scoring.

## Interview Questions

- Which metrics separate diagnosis quality from action safety?
- How would you evaluate refusal and escalation behavior?
