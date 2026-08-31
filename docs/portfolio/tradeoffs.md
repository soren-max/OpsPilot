# Engineering Trade-offs

| Choice | Why OpsPilot v1 chose it | Cost / when to reconsider |
| --- | --- | --- |
| LangGraph vs custom state machine | Explicit graph, interrupt/resume, checkpoint ecosystem | Framework coupling; custom engine may fit simpler or highly regulated runtimes |
| Ansible vs raw SSH | Fixed modules/playbooks, inventory ownership, audit-friendly typed variables | More packaging/runtime overhead; direct SSH is smaller but dangerously broad |
| Qdrant hybrid vs dense-only | Exact tokens plus semantic candidates; RRF avoids score calibration | More index/query complexity; current lexical dataset lets sparse outperform hybrid |
| MCP vs direct HTTP adapter | Standard typed discovery/transport and portable interoperability | Larger trust surface and protocol machinery; direct HTTP is simpler for one stable service |
| PostgreSQL checkpoint vs memory | Survives process restart and supports stable workflow identity | Operational dependency and migration work; memory remains useful for unit tests only |
| Transactional Outbox vs direct dispatch | Atomically preserves dispatch intent with business state | Dispatcher/reconciler complexity; direct calls are acceptable only when loss/duplication is harmless |
| Deterministic Policy vs Risk Agent | Reproducible, reviewable enforcement that fails closed | Less contextual nuance; a future Risk Agent must remain advisory and unable to lower risk |
| Harness vs Ansible | Harness models governed async delivery; Ansible handles bounded host remediation | Two backends add routing/status complexity; operator profiles decide, never the caller |
| Synthetic Lab vs production environment | Public, safe, deterministic, credential-free evidence | Cannot prove production scale, IAM, data distribution, failure rates, or operator outcomes |

The v1 architecture freezes these boundaries. GitOps, a risk reviewer, and production hardening are
future work rather than implicit promises.

