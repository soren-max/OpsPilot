# ADR 0001: Structured Actions over Arbitrary Shell

## Status

Accepted

## Context

Model-generated commands are difficult to authorize, validate, reproduce, and audit.

## Decision

Use `LLM → Structured Action → Policy → Executor`. Every action has a strict schema and unknown
fields are forbidden. No arbitrary shell action exists.

## Consequences

Capabilities grow deliberately and require models, policy, adapter mapping, and tests. This is
less flexible than shell generation and materially safer.

## Alternatives Considered

Direct shell generation, constrained command strings, and post-generation command filtering were
rejected because strings remain an unsafe authorization boundary.
