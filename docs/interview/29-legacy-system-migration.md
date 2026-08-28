# Legacy System Migration

**Question:** How would you migrate an SSH-based incident tool without a big-bang rewrite?

**Answer:** Use a Strangler adapter for selected semantic operations. Preserve the caller-facing
business intent temporarily, but translate it into OpsPilot's structured action, deterministic
Policy, durable approval, governed execution and verification chain. Reject unsafe command-shaped
requests. Expand coverage only after each target reaches an explicit readiness level.
