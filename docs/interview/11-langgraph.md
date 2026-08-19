# LangGraph Incident Orchestration

Status: **Implemented in M2**

## Why LangGraph instead of a giant prompt?

Incident response has named stages, deterministic policy branches, side effects, pause points,
and failure semantics. A StateGraph makes those transitions testable and observable. A prompt
cannot be the authority for policy or infrastructure execution.

## Is LangGraph making the model smarter?

No. It supplies state, control flow, checkpoints, retry boundaries, interrupts, and traces. M2
uses no LLM at all: `DeterministicInvestigator` returns structured hypotheses, diagnoses, action
proposals, evidence references, confidence, and a decision summary.

## Why not save chain-of-thought?

Hidden reasoning is neither a stable contract nor an appropriate audit artifact. OpsPilot saves
evidence references and concise structured decisions that operators can inspect.

## Why must nodes be idempotent?

Checkpoint replay or a worker retry can run a node more than once. Stable workflow IDs,
idempotency keys, stored side-effect references, version checks, and deduplicated workflow events
prevent repeated actions and misleading audit trails.
