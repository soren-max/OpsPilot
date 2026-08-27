# 28 — Harness governed delivery

**Why is Harness a backend rather than an Agent?** It executes an allowlisted delivery pipeline
after Policy and approval. It does not reason, authorize, or orchestrate the incident workflow.

**What may the caller provide?** A typed business action. Account, org, project, API key, pipeline,
and permitted input shape are operator-owned. Provider output is bounded and treated as data.

**Is real Harness required in CI?** No. CI validates trigger, status mapping, indeterminate dispatch,
and reconciliation with a fake HTTP server. SaaS integration is explicit and opt-in.
