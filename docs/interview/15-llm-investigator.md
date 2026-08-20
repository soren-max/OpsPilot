# LLM Investigator

OpsPilot uses an LLM for one transformation: bounded Evidence to a structured investigation. The
workflow owns orchestration; capability ports own observation; policy and HITL own authorization.
This division keeps model creativity out of execution control and preserves a deterministic offline
baseline.

Provider selection, model, key, timeout, retry count, and mutating-action confidence threshold are
operator settings. Incident or API input cannot change them. A real provider failure is recorded and
returned explicitly, never hidden by switching to deterministic behavior.
