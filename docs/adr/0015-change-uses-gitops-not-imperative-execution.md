# ADR 0015: CHANGE Uses GitOps, Not Imperative Execution

Status: Accepted

Desired-state changes require a declarative, versioned review artifact and pull-based continuous
reconciliation. Therefore `CHANGE` creates a branch, commit, and PR through an operator profile;
Argo CD observes the merged revision. `REMEDIATE` remains the bounded Ansible/Harness execution path.

OpsPilot does not call kubectl, Kubernetes mutation APIs, rollout undo, or arbitrary Argo sync for a
CHANGE. This adds review latency but preserves history, drift correction, and a governance boundary.
