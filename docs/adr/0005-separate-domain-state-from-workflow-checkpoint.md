# ADR 0005: Separate domain state from workflow checkpoints

Status: Accepted

## Context

Incident status, evidence, hypotheses, diagnoses, actions, and audit events are durable business
facts. LangGraph also needs execution position and local references so a graph can checkpoint and
eventually resume. Treating either store as a replica of the other would create conflicting truth.

## Decision

The Incident database remains the domain source of truth. Every business mutation continues
through existing application services and domain lifecycle rules. `WorkflowRun` stores durable
OpsPilot metadata such as graph version, status, current node, timestamps, and a safe error.

The LangGraph checkpointer stores only serializable execution state and node position. Graph state
contains identifiers and structured decision fields, never ORM records, database sessions,
executor instances, HTTP requests, raw logs, embeddings, or hidden chain-of-thought.

Each WorkflowRun owns one stable LangGraph thread: `thread_id = workflow_id`. An Incident may own
many WorkflowRuns. M2 provides a checkpoint port and an in-memory adapter for development and
tests; durable Postgres persistence and approval resume are M4 work.

## Consequences

Nodes must reload domain facts through application capabilities and side-effecting nodes must be
idempotent under replay. Losing an M2 memory checkpoint does not lose Incident facts, but it does
lose resumable execution position. Production deployments must not describe the memory adapter
as durable persistence.
