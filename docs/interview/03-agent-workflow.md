# Agent Workflow

Status: **Planned**

## Concept

An explicit workflow represents investigation as state transitions instead of one open-ended
prompt.

## Where in OpsPilot

`IncidentState` is a minimal boundary; LangGraph implementation is planned for M2.

## Why

Explicit evidence, hypotheses, decisions, and interrupts are testable and auditable.

## Trade-offs

State machines add schemas, persistence, and recovery semantics.

## Failure Modes

Loops, stale state, duplicate execution, invalid resume, and skipped evidence collection.

## Interview Questions

- Why use workflow state instead of hidden chain-of-thought?
- How would checkpoint replay remain idempotent?
