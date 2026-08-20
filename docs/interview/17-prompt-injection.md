# Prompt Injection

Logs, tickets, alerts, and operator notes are attacker-influenceable data. The v1 system prompt marks
all Evidence untrusted and says embedded role claims, commands, approval requests, and instruction
overrides must not be followed. Context is bounded and serialized as data.

Prompting is defense in depth. Enforceable controls follow generation: strict schema, incident-local
Evidence ID validation, supported-action validation, confidence rules, deterministic policy, and
approval. Adversarial fixtures cover instruction override, shell requests, fabricated IDs, unsupported
actions, confidence overflow, and injected authorization fields.
