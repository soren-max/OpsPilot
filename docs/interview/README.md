# Interview Notes

[English](README.md) | [简体中文](../zh-CN/interview/README.md)

Topic notes from the design interviews, one file per topic. The notes are English only; a Chinese
translation of this index lives under `../zh-CN/interview/`. Note: two files share the `08-`
prefix (`08-incident-domain.md` and `08-portable-execution-boundary.md`); this is a historical
numbering quirk and the files are intentionally not renamed.

## Interview Preparation Index

| Topic | Start here | Core point |
| --- | --- | --- |
| Architecture | [Agent Workflow](03-agent-workflow.md) | Explicit orchestration and narrow boundaries replace an open-ended agent loop. |
| Agent Workflow | [Agent Workflow](03-agent-workflow.md) | State transitions make decisions observable and testable. |
| LangGraph | [LangGraph Incident Orchestration](11-langgraph.md) | Checkpoint state is distinct from durable domain state. |
| Evidence Grounding | [Evidence Grounding](14-evidence-grounding.md) | Conclusions cite incident-local, validated Evidence IDs. |
| Prompt Injection | [Prompt Injection](17-prompt-injection.md) | Untrusted evidence cannot bypass schema, grounding, policy, or approval. |
| Evaluation | [Agent Evaluation](18-agent-evaluation.md) | Deterministic fixtures cover grounding, action accuracy, and safety. |
| RAG Memory | [RAG Incident Memory](19-rag-incident-memory.md) | Resolved incident projections become sourced historical context. |
| Hybrid Retrieval | [Hybrid Retrieval](20-hybrid-retrieval.md) | Dense and sparse ranks are fused with RRF. |
| Retrieval Eval | [Retrieval Evaluation](21-retrieval-evaluation.md) | Recall, MRR, root-cause hits, and latency are regression tested. |
| MCP Boundary | [MCP Capability Boundary](22-mcp-capability-boundary.md) | MCP exposes ports without replacing authorization or orchestration. |
| MCP Security | [MCP Security](23-mcp-security.md) | Allowlisting, scopes, ownership, Policy, and HITL contain protocol threats. |
| Infrastructure Telemetry | [Agent Infrastructure Observability](24-agent-infrastructure-observability.md) | Safe trace propagation connects MCP to capability work. |
| Execution Safety | [Agent Safety](04-agent-safety.md) | Structured actions and fail-closed policy constrain authority. |
| Observability | [Observability Capabilities](13-observability-capabilities.md) | Typed ports replace arbitrary PromQL and LogQL. |
| Ansible Boundary | [Executor and Ansible](06-executor-and-ansible.md) | Fixed mappings keep transport and playbook selection outside model control. |

## Agent Workflow

- [Agent Workflow](03-agent-workflow.md) — **Implemented in M2**
  An explicit workflow models investigation as state transitions instead of one open-ended
  prompt. M1C provides the Incident, Evidence, Hypothesis, Diagnosis, and AuditEvent boundaries;
  M2 adds a LangGraph workflow that composes them while keeping node names separate from stable
  Incident business status.
- [Human in the Loop](05-hitl.md) — **Partial** (durable interrupt/resume planned for M4)
  HITL pauses a state-changing workflow until an authorized person reviews the exact action.
  Medium-risk policy results already block execution without approval; durable workflow
  interrupt and checkpoint integration is planned.
- [Tool Calling](02-tool-calling.md) — **Planned**
  Planned capability for a model to select a narrow capability port and validated arguments,
  which limits model authority and makes observations explicit.

## LangGraph

- [LangGraph Incident Orchestration](11-langgraph.md) — **Implemented in M2**
  A StateGraph makes named stages, deterministic policy branches, side effects, pause points,
  and failure semantics testable and observable. M2 runs with no LLM at all — a
  `DeterministicInvestigator` produces the structured investigation.
- [Workflow Persistence](12-workflow-persistence.md) — **Boundary in M2**
  LangGraph's `thread_id` maps to `workflow_id`; checkpoints record where graph execution was,
  while the Incident database records what happened operationally. Business mutations always go
  through application services, even when a node is replayed.

## Incident Domain

- [Incident Domain](08-incident-domain.md) — **Implemented in M1C**
  Evidence is a first-class concept: observations keep type, source, time, provenance,
  collector, and stable identity. Raw logs and metric series are stored as bounded excerpts and
  summaries rather than dumped into the Incident database.
- [Incident Memory](10-incident-memory.md) — **Knowledge projection in M1C; retrieval planned for M6**
  Only resolved or closed incidents enter memory, so provisional hypotheses are never indexed
  as trusted history. The Action domain stays incident-free; an application-layer
  `IncidentActionLink` provides traceability.

## Audit

- [Audit and Event Model](09-audit-and-event-model.md) — **Implemented in M1C**
  Append-only `AuditEvent` (ORM update/delete hooks reject mutation) is committed in the same
  transaction as state mutation, so no state change exists without its evidence trail.
  Corrections become new events linked by correlation and causation identifiers.

## Observability

- [Observability Capabilities](13-observability-capabilities.md) — **M3A**
  Typed, bounded Prometheus, Loki, Ticket, and Service Health capability ports accept
  `MetricQuery` and exact selectors — never PromQL or LogQL — and collect provenance-preserving
  Incident Evidence. Direct HTTP integration avoids coupling investigation to dashboards or
  user sessions.

## Evidence Grounding

- [Evidence Grounding](14-evidence-grounding.md) — **M3A/M3B**
  Every normalized observation records source, opaque source reference, observed/collection
  time, collector, bounded content, and a deduplication fingerprint. Graph state holds only
  evidence IDs, never raw logs, keeping replay deterministic and context bounded.

## LLM Investigator

- [LLM Investigator](15-llm-investigator.md) — **M3B**
  The LLM performs exactly one transformation: bounded Evidence to a structured investigation.
  The workflow owns orchestration, capability ports own observation, and policy/HITL own
  authorization; provider settings are operator-owned and cannot be changed by incident input.

## Structured Output

- [Structured Output](01-structured-output.md) — **Implemented**
  Structured output converts model intent into schema-validated Pydantic data rather than
  executable text, so policy and adapters receive typed, bounded inputs that reject unknown
  fields.
- [Structured Output provider API](16-structured-output.md) — **M3B**
  The core provider API returns `InvestigationModelOutput` bounded by Pydantic v2 with no place
  for approval, commands, credentials, PromQL, LogQL, or tool calls. The stored decision summary
  is an auditable conclusion, not hidden chain-of-thought.

## Prompt Injection

- [Prompt Injection](17-prompt-injection.md) — **M3B**
  All Evidence is marked untrusted and serialized as data; prompting is defense in depth.
  Enforceable controls follow generation: strict schema, incident-local evidence-ID validation,
  supported-action validation, confidence rules, deterministic policy, and approval, covered by
  adversarial fixtures.

## Evaluation

- [Evaluation](07-evaluation.md) — **Foundation in M3B; broader evaluation planned**
  Deterministic action-safety tests exist today; M3B adds `InvestigationEvalCase` fixtures,
  safety cases, and metrics. Full incident datasets and large-scale model evaluation are planned
  for later milestones.
- [Agent Evaluation](18-agent-evaluation.md) — **M3B**
  Reusable `InvestigationEvalCase` fixtures report Evidence Precision/Recall, Action Accuracy,
  Grounding Validity, Unsupported Action Rate, and more. The same cases run deterministically,
  against fake providers, or with an optional real model without making CI depend on an API key.

## Ansible / Execution Safety

- [Legacy System Migration](29-legacy-system-migration.md) — **M8.5**
  Strangler adapters move selected operations into the governed path without a big-bang rewrite.
- [SSH vs Service Abstraction](30-ssh-vs-service-abstraction.md) — **M8.5**
  SSH remains an Ansible transport detail while the application expresses semantic actions.
- [Deployment Knowledge as Configuration](31-deployment-knowledge-as-configuration.md) — **M8.5**
  Strict operator profiles capture environment knowledge without exposing arbitrary execution.

- [Executor and Ansible](06-executor-and-ansible.md) — **Implemented**
  The `ActionExecutor` port (`MockActionExecutor`, `AnsibleActionExecutor`, fixed Playbooks)
  isolates domain actions from infrastructure transports — the domain never sees SSH, subprocess
  syntax, inventory paths, or Ansible internals.
- [Portable Execution Boundary](08-portable-execution-boundary.md) — **Implemented in M1B**
  The strict `ActionRequest` lets policy authorize the exact object sent to an adapter, so an
  agent cannot smuggle command syntax, inventory, or credentials through the API. Deterministic
  policy evaluates authorization facts first; an LLM risk review may add context but cannot
  override a deny.
- [Agent Safety](04-agent-safety.md) — **Partial**
  Agent safety combines constrained capabilities, deterministic authorization, approval, and
  audit. `ActionPolicyEngine`, strict models, target allowlists, and adapter mappings form the
  M1A core.
