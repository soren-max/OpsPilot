# Workflow Persistence

Status: **Implemented boundary in M2**

## What is `thread_id`?

It is LangGraph's stable identity for one execution thread. OpsPilot maps it to `workflow_id`, not
to a new random request ID. One Incident may have multiple WorkflowRuns and therefore multiple
threads.

## Why is a checkpoint not the business database?

A checkpoint answers where graph execution was and which local references it held. The Incident
database answers what happened operationally: status, evidence, diagnosis, action, and audit.
Business mutations always use application services even when a node is replayed.

## What does WorkflowRun add?

It gives OpsPilot queryable metadata independent of LangGraph internals: graph name/version,
actor, status, current node, start/finish/checkpoint timestamps, idempotency, and safe failure.

## Is M2 durable across process restarts?

Domain facts and WorkflowRun metadata are durable. The configured M2 checkpoint adapter is memory
only, so resumable graph position is not production-durable. M4 will add Postgres checkpointing
and identity-bound approval/resume APIs.
