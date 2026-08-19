# Agent Safety

Status: **Partial**

## Concept

Agent safety combines constrained capabilities, deterministic authorization, approval, and audit.

## Where in OpsPilot

`ActionPolicyEngine`, strict models, target allowlists, and adapter mappings form the M1A core.

## Why

Helpful model output is not equivalent to operational authority.

## Trade-offs

Fail-closed behavior can block legitimate work until explicit rules exist.

## Failure Modes

Policy bypass, confused deputy behavior, approval replay, excessive scope, and unsafe logs.

## Interview Questions

- Why can an LLM risk reviewer not be the final authorization layer?
- How do defense-in-depth allowlists help?
