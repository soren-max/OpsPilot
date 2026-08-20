# Structured Output

The core provider API returns `InvestigationModelOutput`, not arbitrary text. Pydantic v2 bounds text,
confidence, reference count, and the `ActionType` enum while forbidding extra fields. There is no
place to return approval, commands, executors, credentials, PromQL, LogQL, or tool calls.

The stored decision summary is a short auditable conclusion, not hidden chain-of-thought. Explicit
workflow state provides observable reasoning stages without asking for or retaining private model
reasoning.
