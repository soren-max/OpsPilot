# 25 — Multi-backend execution

**Why not add an executor `if/else`?** A stable backend port, descriptors, and profiles separate
business actions from provider mechanics and make routing deterministic.

**Who selects Harness?** Operator configuration. The LLM proposes an action; Policy authorizes;
HITL approves; the router selects a profile.

**What does backend success mean?** Only that execution completed. Independent verification decides
whether the incident was remediated.
