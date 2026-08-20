# LLM Investigator

M3B adds one narrow AI capability: converting bounded, durable Incident Evidence into a validated
`InvestigationResult`. It is not a chatbot or an execution agent.

```text
Capabilities -> durable Evidence -> EvidenceContextBuilder -> LLMIncidentInvestigator
             -> strict InvestigationModelOutput -> InvestigationGuard -> action proposal
             -> ActionPolicyEngine -> approval/execution boundary
```

`IncidentInvestigator` remains the workflow port. `DeterministicInvestigator` is the offline and CI
baseline; `LLMIncidentInvestigator` depends on `StructuredReasoningProvider`. Production mode is an
explicit operator choice. Provider failure never silently switches modes.

The v1 prompt sends summaries, bounded excerpts, safe metadata, and evidence IDs only. Selection is
deterministic, prioritizes health/alerts/metrics, preserves source diversity, and enforces count and
character budgets. Evidence is explicitly marked untrusted: log, ticket, and operator text cannot
issue instructions. The prompt and raw provider response are not persisted.

The strict schema forbids extra fields and exposes no command, query language, executor, credential,
risk override, approval, or tool-call field. Evidence references must be unique, supplied in the
current incident context, and non-empty for a diagnosis or action. Unsupported `ActionType` values,
low-confidence mutating proposals, and inconsistent insufficient-evidence outputs fail closed.

Only the auditable conclusion is retained: statement, root cause, decision summary, confidence,
uncertainty, evidence references, provider/model/prompt version, latency, and optional token counts.
Private chain-of-thought, raw prompts, authorization headers, and raw evidence bodies are excluded.

The first adapter uses OpenAI's Responses API with strict JSON Schema, `store=false`, a fixed
operator-owned endpoint, no tools, bounded responses, and typed timeout/rate-limit/malformed errors.
See the [official Responses API reference](https://developers.openai.com/api/reference/java/resources/beta/subresources/responses).

M3B does not add durable HITL, RAG, MCP, arbitrary tool use, or autonomous remediation.
