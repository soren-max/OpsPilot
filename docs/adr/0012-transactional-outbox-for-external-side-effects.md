# ADR 0012: Transactional outbox for external side effects

Status: Accepted

## Decision

Persist the execution and dispatch outbox entry in one database transaction. Dispatch later from a
leased, concurrency-safe worker. A dispatch timeout or expired in-flight lease is indeterminate and
must be reconciled; it must not be retried automatically.

## Consequences

Database state can no longer claim an action was queued without a durable dispatch message. The
design deliberately prefers operator reconciliation over duplicating an external side effect.
