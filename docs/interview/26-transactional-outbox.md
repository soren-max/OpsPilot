# 26 — Transactional outbox

**What problem does it solve?** It removes the database/external-HTTP dual write. Execution and
outbox records commit atomically, and a separate dispatcher performs the side effect.

**How is concurrency handled?** PostgreSQL claims pending rows with `FOR UPDATE SKIP LOCKED` and a
bounded lease. One execution has one uniquely constrained outbox entry.
