# ADR 0009: Historical incident memory is context, not evidence

## Status

Accepted

## Decision

Retrieved historical incidents are represented as `RetrievedKnowledge`, separately from current
Incident Evidence. Investigator output has independent `evidence_ids` and `knowledge_refs`.
Evidence grounding validates only current Evidence IDs for diagnoses and actions.

## Rationale

A similar past incident can be useful while still being wrong about the present incident. Treating
similarity as confidence or evidence would allow stale or injected history to manufacture facts and
cross the execution boundary. Retrieval score therefore means ranking similarity only.

## Consequences

Policy, HITL, ActionService, and Executor remain unchanged. Prompts label both sections as
untrusted data. Checkpoints keep references, not embeddings or backend responses.
