# Advanced Local Demo

Run `make demo-full` after the ten-minute core walkthrough. It adds local Qdrant historical memory
and the OpsPilot MCP server while keeping the deterministic investigator and synthetic services.
No paid service is required.

The advanced profile demonstrates two boundaries without changing the safety story:

- Historical incidents appear as context, never current Evidence or authorization.
- MCP exposes typed interoperability capabilities; Policy and durable HITL remain authoritative.

OpenAI is an explicit manual opt-in and is not enabled by either demo profile.
