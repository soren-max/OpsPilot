# ADR 0014: Legacy Migration Uses Strangler Adapters

## Status

Accepted.

## Decision

Legacy callers and ticket systems integrate through narrow adapters around existing OpsPilot
application and capability ports. Selected operations move incrementally through Policy, durable
HITL, governed execution and independent verification. Unsafe legacy semantics return a migration
requirement rather than bypassing controls.

## Consequences

Migration is not a big-bang replacement:

1. Phase A — the legacy system owns its existing implementation.
2. Phase B — selected operations enter OpsPilot through compatibility adapters.
3. Phase C — OpsPilot owns governed operations.
4. Phase D — the private deployment removes its legacy `ServiceSSH` path.
