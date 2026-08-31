# Human in the Loop

Status: **Implemented in M4**

## Concept

HITL pauses a state-changing workflow until an authorized person reviews the exact action.

## Where in OpsPilot

Medium-risk policy results block execution without approval. M4 adds identity-bound durable
approval, PostgreSQL checkpoint resume, duplicate-decision conflict, and idempotent replay.

## Why

Human review owns impact and authorization for mutations.

## Trade-offs

Approval introduces latency and requires identity, expiry, and replay controls.

## Failure Modes

Self-approval, stale approval, action substitution, duplicate resume, and approval fatigue.

## Interview Questions

- What must an approval fingerprint bind?
- When should approval expire?
