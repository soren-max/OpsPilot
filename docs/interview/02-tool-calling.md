# Tool Calling

Status: **Planned**

## Concept

Tool calling lets a model select a narrow capability and validated arguments.

## Where in OpsPilot

Future capability ports will produce evidence or structured action proposals.

## Why

It limits model authority and makes observations explicit.

## Trade-offs

More tools improve precision but increase routing and evaluation complexity.

## Failure Modes

Wrong tool selection, invalid arguments, duplicate calls, stale results, and prompt injection.

## Interview Questions

- What belongs in a capability rather than a prompt?
- Where should tool authorization occur?
