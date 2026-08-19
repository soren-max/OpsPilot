# Audit and Event Model

Status: **Implemented in M1C**

## Why append-only AuditEvent?

An audit history must describe what happened at the time, not the latest preferred story.
Application code exposes append and list only, while ORM update and delete hooks reject mutation.
Corrections become new events linked by correlation and causation identifiers.

## Why put audit and state mutation in one transaction?

Committing state without its evidence trail creates an unauditable incident. Committing an event
without state creates a false claim. M1C flushes both in one SQLAlchemy transaction and rolls the
whole unit back if either insert or versioned update fails.

## How is sensitive data kept out of audit payloads?

Event metadata uses an explicit field allowlist and scalar values only. Summaries and allowed
references reuse redaction for password, token, secret, private-key, command, host, and account
patterns. Tool responses and Evidence metadata are never dumped wholesale into AuditEvent.

## Why model AGENT and TOOL actor types before they execute?

Actor type is a stable audit vocabulary. M1C introduced HUMAN events; M2 now emits real SYSTEM
workflow lifecycle and node events with stable correlation IDs and safe scalar metadata.
