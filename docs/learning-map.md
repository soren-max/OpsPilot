# AI Application Learning Map

This map connects concepts to real or explicitly planned OpsPilot work. It is inspired by common
LLM application curricula, including `Lordog/dive-into-llms`, without copying course code.

| AI Knowledge | OpsPilot Mapping | Status |
| --- | --- | --- |
| Prompting | Incident intent and structured task instruction | Planned |
| Structured Output | `ActionRequest` and `RiskAssessment` | Implemented |
| CoT / Task Decomposition | Explicit workflow state, not hidden reasoning | Implemented |
| ReAct | Workflow node → capability → observable state update | Implemented |
| Tool Calling | Capability layer | Planned |
| Agent | Stateful incident orchestration | Implemented |
| Agent Safety | Deterministic policy + risk + approval boundary | Implemented |
| HITL | M4 durable interrupt/checkpoint/resume | Planned |
| RAG / Memory | M6 retrieved knowledge context | Boundary only |
| LangGraph | Incident StateGraph and workflow trace | Implemented |
| MCP | Optional future tool boundary | Planned |
| Evaluation | Incident dataset and safety evaluation | Planned |
| Observability | Agent, tool, action, and approval traces | Partial |

OpsPilot does not expose, store, or depend on hidden chain-of-thought. Auditable artifacts are
evidence, hypotheses, decision summaries, action reasons, and risk reasons.

LangGraph does not make a model smarter. Here it supplies explicit state, control flow,
checkpoint hooks, retry boundaries, pause points, and node-level observability.
