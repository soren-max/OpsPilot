# What OpsPilot Does NOT Claim

OpsPilot v1.0 is a personal, synthetic portfolio system. It does not claim:

- production deployment or enterprise production validation;
- an autonomous SRE replacement;
- production-proven exactly-once delivery (the design is at-least-once-aware with idempotency,
  UNKNOWN state, and reconciliation);
- full enterprise IAM, tenancy, HA, disaster recovery, or compliance certification;
- training on proprietary or company incidents;
- benchmarking against production traffic, incident distributions, or operator outcomes;
- that deterministic hash embeddings represent a production embedding model;
- that the deterministic investigator is a broad diagnostic model—its checked-in M3B fixture
  accuracy is intentionally reported and shows limited category coverage;
- real Harness SaaS execution unless an explicit opt-in run says otherwise;
- that an optional OpenAI evaluation ran when the artifact says `NOT RUN`;
- a real legacy company environment—the SSH compatibility target is synthetic;
- complete security coverage beyond the enumerated scenario and contract tests.

OpenAI, real Harness SaaS, and remote MCP are optional. The canonical demo needs none of them.

## Closeout documentation audit

- **BLOCKER:** none found after the final Portfolio Check.
- **FUTURE WORK:** M9 GitOps; M10 advisory Risk Reviewer/advanced evaluation; M11 production
  hardening and operational observability.
- **INTENTIONAL LIMITATION:** no RAGFlow adapter, no real Harness/OpenAI run in the default artifact,
  synthetic Lab/legacy targets only, and no production claim.

Older ADR/learning documents may use “planned” while explaining the historical design decision or a
named future milestone; those statements are not incomplete v1 functionality.
