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

For a persistent offline walkthrough across separate processes:

```bash
make gitops-lab-up
make gitops-lab-status
# Copy the printed Change ID into the following commands.
make gitops-approve CHANGE_ID=<id>
make gitops-review CHANGE_ID=<id>
make gitops-merge CHANGE_ID=<id>
make gitops-reconcile CHANGE_ID=<id>
make gitops-lab-down
```

The default state directory is `.cache/gitops-lab`; `OPSPILOT_GITOPS_LAB_STATE` can select an
isolated directory. SQLite stores OpsPilot records and JSON stores simulated external Git state.
`status` is read-only. `review` and `merge` persist separate external synthetic reviewer actions;
merge fails without review. Reconciliation observes these actions in a later process. These
commands do not install Kind, start Argo, or access GitHub. The offline verifier is a fixture;
it is not evidence of real application recovery. `make gitops-lab-reset` removes only this lab's
named state files. Do not point its state directory at an application database.

The HTTP API and console prepare the semantic preview before approval. Approval sends the
reviewed plan fingerprint. If the source revision or preview changes, prepare and review again.
Git dispatch rechecks current Evidence, approval age, source revision, policy and planned bytes.

Real GitHub integration is optional and manual. Configure an allowlisted repository/base branch,
GitHub token, Argo endpoint/token, and optional webhook secret through operator environment settings.
CI never uses a PAT or creates a real PR.
