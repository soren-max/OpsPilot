# ADR 0010: MCP Is an Interoperability Boundary, Not an Authorization Boundary

- Status: Accepted
- Date: 2026-08-20

## Decision

Use MCP `2026-07-28` as an adapter around application capability ports. Protocol annotations,
discovery, transport, and remote claims never authorize work. Policy, evidence ownership, durable
approval, and fixed executor mappings remain authoritative. Only allowlisted semantic tools are
exposed or consumed; the mutating surface proposes remediation but cannot execute it.

## Consequences

External hosts gain standard typed interoperability and tracing without arbitrary Python, shell,
query-language, or executor access. Remote MCP content stays untrusted. LangGraph remains the
durable orchestration authority.
