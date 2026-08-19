# Human in the Loop

Status: **Partial**

## Concept

HITL pauses a state-changing workflow until an authorized person reviews the exact action.

## Where in OpsPilot

Medium-risk policy results block execution without approval. Durable workflow interrupt and
checkpoint integration is planned.

## Why

Human review owns impact and authorization for mutations.

## Trade-offs

Approval introduces latency and requires identity, expiry, and replay controls.

## Failure Modes

Self-approval, stale approval, action substitution, duplicate resume, and approval fatigue.

## Interview Questions

- What must an approval fingerprint bind?
- When should approval expire?
