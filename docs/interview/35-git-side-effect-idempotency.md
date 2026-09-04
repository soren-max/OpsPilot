# Git Side-effect Idempotency

Network loss after PR acceptance creates ambiguity. Retrying may create two changes, so OpsPilot uses
a stable Change ID, deterministic branch, action fingerprint, approval ID, commit correlation, and
delivery ID. `UNKNOWN` triggers lookup and reconciliation; uncertainty is not rendered as failure.
