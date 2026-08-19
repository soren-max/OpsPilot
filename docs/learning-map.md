# AI Application Learning Map

This map connects concepts to real or explicitly planned OpsPilot work. It is inspired by common
LLM application curricula, including `Lordog/dive-into-llms`, without copying course code.

| AI Knowledge | OpsPilot Mapping | Status |
| --- | --- | --- |
| Prompting | Incident intent and structured task instruction | Planned |
| Structured Output | `ActionRequest` and `RiskAssessment` | Implemented |
| CoT / Task Decomposition | Explicit workflow state, not hidden reasoning | Partial |
| ReAct | Agent → Tool → Observation model | Planned |
| Tool Calling | Capability layer | Planned |
| Agent Safety | Policy + risk + approval boundary | Partial |
| RAG / Memory | Incident and playbook retrieval | Planned |
| LangGraph | Incident state machine | Planned |
| MCP | Optional future tool boundary | Planned |
| Evaluation | Incident dataset and safety evaluation | Planned |
| Observability | Agent, tool, action, and approval traces | Partial |

OpsPilot does not expose, store, or depend on hidden chain-of-thought. Auditable artifacts are
evidence, hypotheses, decision summaries, action reasons, and risk reasons.
