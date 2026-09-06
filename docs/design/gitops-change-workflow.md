# Governed GitOps Change Workflow

## Decision boundary

OpsPilot has three execution semantics:

- `OBSERVE` reads current state and produces Evidence.
- `REMEDIATE` performs a bounded operational recovery through the governed execution plane.
- `CHANGE` mutates desired state through Git and never calls `kubectl`, Kubernetes mutation APIs,
  or an arbitrary Argo CD sync.

The CHANGE path under acceptance review is:

```text
Evidence -> ChangeIntent -> Change Policy -> OpsPilot approval -> ChangeSet
-> transactional outbox -> deterministic branch/commit -> pull request -> Git review
-> external merge -> Argo CD pull/reconcile -> revision + sync + health observation
-> independent OpsPilot verification -> incident resolution
```

This follows the [OpenGitOps principles](https://opengitops.dev/): desired state is declarative,
versioned and immutable, pulled automatically, and continuously reconciled. M9 supports plain Kubernetes Deployment
manifests with two semantic mutations: `ROLLBACK_IMAGE` and `SCALE_REPLICAS`.

## Contracts

`ChangeIntent` contains incident/workflow identity, service, environment, a semantic resource
reference, reason, Evidence IDs, requester, and the bounded change-specific value. Its strict schema
has no repository, branch, path, namespace, cluster, credential, YAML, patch, shell, kubectl, or
Argo application field.

`GitOpsApplicationProfile` is operator-owned. It selects the repository, base branch, manifest
path, Argo application, allowed resources/fields/registries, replica ceiling, verification profile,
and known-good immutable image digest.

`PlainKubernetesChangePlanner` resolves exactly one resource. Ambiguity, missing state, multiple
containers for a rollback, forbidden resource kinds, privileged workload fields, image mutations
landing anywhere but the operator known-good immutable digest, and changes outside the profile
fail closed. The resulting `ChangeSet` stores a semantic mutation,
blast radius, evidence correlation, source revision, bounded changed file, and a raw technical diff.

## Durable lifecycle

The canonical statuses deliberately preserve separate facts:

```text
WAITING_APPROVAL -> QUEUED -> WAITING_REVIEW -> APPROVED_FOR_MERGE -> MERGED
-> RECONCILING -> SYNCED -> HEALTHY -> RESOLVED
```

`PR_CREATED != deployed`, `MERGED != SYNCED`, `SYNCED != HEALTHY`, and
`HEALTHY != RESOLVED`. External waits end the active graph/controller turn after state is persisted;
workers do not block while a human reviews a PR. Polling remains the baseline. Authenticated webhook
events are a wake-up signal, not an authorization source.

The API prepares a semantic preview before Gate A and requires its fingerprint on approval.
Source revision drift invalidates the reviewed plan. Dispatch rechecks Evidence freshness,
approval expiry, policy and exact planned bytes before any Git write. A durable claim precedes
external writes, and the branch and commit checkpoints are saved independently. Exceptions after
a possible write enter UNKNOWN; reconciliation must match the durable approved commit.

The worker runs bounded controller ticks through LangGraph. Graph input contains a change ID;
caller-provided approval, merge, sync or verification booleans cannot authorize progress. The
controller reads durable SQL records and current operator configuration on each tick. Production
verification uses the existing health, metrics and logs capability ports and saves current Evidence.

## Ports and adapters

- `GitChangeProvider`: read base/file, create branch/commit/PR, and observe PR/review/revision. It
  intentionally has no review, approval, or merge method.
- `GitHubGitChangeProvider`: bound to one operator-configured repository and base branch.
- `FakeGitChangeProvider`: deterministic branch/commit/PR lifecycle for CI and the synthetic lab.
- `GitOpsReconciler`: read application revision, sync, health, and resource status; optional refresh.
- `ArgoCDGitOpsReconciler`: read-only Argo CD API adapter with an application allowlist.

[Argo CD hooks and sync waves](https://argo-cd.readthedocs.io/en/stable/user-guide/sync-waves/)
may order resources, but neither an Argo diff nor a PostSync hook replaces OpsPilot policy or
independent current-state verification.

## Revert

A failed verification never triggers an automatic production rollback. `RevertProposal` creates a
new governed change that repeats policy, OpsPilot approval, Git review, merge, reconciliation, and
verification.
