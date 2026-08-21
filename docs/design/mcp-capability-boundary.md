# MCP Capability Boundary

OpsPilot targets MCP `2026-07-28` with official Python SDK `2.0.0`. The adapter exposes existing
typed ports; it does not create a second agent framework or authorization system.

```text
MCP Client -> stdio / stateless Streamable HTTP -> MCPServer
           -> fixed McpCapabilityBroker -> typed observe / knowledge ports
                                      \-> governed proposal -> Policy -> HITL -> Executor
```

The catalog is a fixed allowlist. Clients cannot supply backend URLs, tool mappings, raw
PromQL/LogQL, Qdrant vectors/filters, inventory, playbooks, commands, or credentials. Tool results
use versioned `structuredContent`; templates expose only bounded incident, evidence, timeline, and
eligible knowledge projections.

Annotations are discovery hints only. Query policy, action policy, evidence ownership, durable
approval, and executor isolation enforce safety. `request_remediation` can only enter the existing
workflow and return `approval_required`; no execute tool exists.

HTTP uses the SDK resource-server middleware and a pluggable verifier. The included verifier checks
JWT signature, issuer, audience, expiry, subject, and scopes. OpsPilot does not issue tokens or run
an authorization server. stdio is trusted local development only.

The controlled client has operator-owned URLs and semantic mappings and never lets a model use
`tools/list` to choose arbitrary remote tools. Remote descriptions, annotations, resources, and
outputs remain untrusted and must pass bounded OpsPilot models.

SDK trace metadata propagates W3C context. Safe spans contain tool/capability names and correlation
identifiers—not tokens, raw logs, prompts, or evidence bodies. MCP Tasks are absent from SDK 2.0.0;
MRTR remains protocol interaction and does not replace Postgres/LangGraph HITL.

Run `make mcp-demo` for official-client stdio and Streamable HTTP interop plus contract evaluation.
MCP Inspector is an optional manual tool, not a CI or production dependency.
