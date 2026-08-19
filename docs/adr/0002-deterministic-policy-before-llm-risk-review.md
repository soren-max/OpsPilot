# ADR 0002: Deterministic Policy before LLM Risk Review

## Status

Accepted

## Context

Model risk judgments are probabilistic and cannot grant infrastructure authority.

## Decision

Apply deterministic action, target, parameter, environment, and approval rules first. A future
LLM risk reviewer may add advice but cannot override a rejection.

## Consequences

Rules are explainable and testable but require maintenance as capabilities expand.

## Alternatives Considered

LLM-only classification and model-plus-keyword blocking were rejected as non-deterministic and
incomplete.
