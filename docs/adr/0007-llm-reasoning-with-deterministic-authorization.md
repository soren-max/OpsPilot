# ADR 0007: LLM reasoning with deterministic authorization

## Status

Accepted

## Decision

Use an LLM only behind a structured reasoning port. Validate its typed output and evidence IDs with
a deterministic guard, then submit any supported action proposal to the existing deterministic
policy and HITL boundary. Preserve the deterministic investigator as an explicit operating mode.

Evidence is untrusted input. Prompt instructions isolate it as data, while schema, grounding, action
allowlists, confidence rules, policy, and approval provide enforceable boundaries. Provider errors
are explicit and auditable; there is no silent fallback.

## Rationale

Structured output removes free-form parsing ambiguity. Grounded IDs make conclusions traceable to
durable records. Private chain-of-thought is neither needed for authorization nor appropriate audit
data, so only concise decision summaries are stored. The model cannot authorize, execute, select an
executor, or alter policy regardless of confidence.

## Consequences

CI and offline demos require no paid API. LLM mode needs operator configuration and can degrade when
the provider fails. Durable approval resume remains M4 work.
