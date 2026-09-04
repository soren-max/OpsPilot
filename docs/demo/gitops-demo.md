# Synthetic GitOps Demo

The default M9 demo is deterministic and offline. It uses the same domain, policy, planner, outbox,
Git provider port, watcher, revision checks, and independent verification as the application, with
in-memory fake Git and Argo adapters. It is synthetic evidence, not a production deployment claim.

```bash
make gitops-e2e
# or only the walkthrough
make gitops-demo
```

The output covers bad deployment, current Evidence, rollback proposal, HIGH policy, OpsPilot
approval, PR creation, an explicitly external synthetic review/merge, pull reconciliation, Synced,
Healthy, independent verification, and final incident resolution.

The checked-in `lab/gitops` directory contains the `gitops-lab` operator profile, bad desired-state
Deployment, Kind cluster configuration, and Argo CD Application template. A live Kind + Argo run is
manual opt-in: install `kind`, `kubectl`, and Argo CD; initialize and serve the synthetic desired-state
directory as a reachable Git repository; replace the Application template repository placeholder;
then create the cluster and apply Argo CD plus the Application. OpsPilot must only observe Argo status;
do not add kubectl apply, patch, rollout undo, or manual sync to the change workflow.

`make gitops-review CHANGE_ID=...` and `make gitops-merge CHANGE_ID=...` are named as external
synthetic reviewer actions. They are deliberately outside the provider port used by OpsPilot.

Real GitHub integration is optional and manual. Configure an allowlisted repository/base branch,
GitHub token, Argo endpoint/token, and optional webhook secret through operator environment settings.
CI never uses a PAT or creates a real PR.
