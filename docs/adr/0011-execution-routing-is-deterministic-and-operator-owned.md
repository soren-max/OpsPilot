# ADR 0011: Execution routing is deterministic and operator-owned

Status: Accepted

## Decision

Route a policy-authorized business action by its typed action and environment through immutable
operator configuration. Validate the selected profile against a backend capability descriptor.
Never accept backend, profile, provider URL, or pipeline identifiers from an LLM, API, or MCP call.

## Consequences

Routing is reproducible and auditable, and a compromised reasoning or interoperability layer cannot
expand execution authority. Adding a backend requires a descriptor, profile, adapter, tests, and
operator configuration rather than another conditional in the workflow.
