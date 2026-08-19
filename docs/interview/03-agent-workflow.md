# Agent Workflow

Status: **Implemented in M2**

## Concept

An explicit workflow represents investigation as state transitions instead of one open-ended
prompt.

## Where in OpsPilot

M1C provides durable Incident, Evidence, Hypothesis, Diagnosis, lifecycle, and AuditEvent
boundaries. M2 adds a LangGraph workflow that composes those application capabilities while
keeping workflow node names separate from stable Incident business status.

## Why

Explicit evidence, hypotheses, decisions, and interrupts are testable and auditable.

## Trade-offs

State machines add schemas, persistence, and recovery semantics.

## Failure Modes

Loops, stale state, duplicate execution, invalid resume, and skipped evidence collection.

## Interview Questions

- Why use workflow state instead of hidden chain-of-thought?
- How would checkpoint replay remain idempotent?
