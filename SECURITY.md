# Security Policy

## Reporting a Vulnerability

Do not open a public issue for a suspected vulnerability or leaked credential. Use GitHub's
private vulnerability reporting feature for this repository. Include affected versions,
reproduction steps, and impact without including live secrets or personal data.

## Security Boundaries

OpsPilot does not accept arbitrary shell actions. Infrastructure changes must be represented by
strict structured actions, assessed by deterministic policy, approved when required, and sent
to a dependency-injected controlled adapter. LLM output is never an authorization decision.

M1B removed application-level SSH, credential management, and service-script execution. Any SSH
used by operator-owned Ansible inventory is an adapter implementation detail and is not exposed
through the Agent, API, application service, or ActionRequest contract.

## Sensitive Data Boundary

Known credential shapes are removed by one sanitizer before Evidence persistence, so model context,
frozen replay, API responses, audit events, JSON logs, and span exception attributes all see the
sanitized value. Covered shapes include `Authorization` headers, JWTs, `api_key`/`token`/`secret`/
`password` assignments (including quoted JSON forms), database DSNs, PEM private-key blocks, cloud
access keys, webhook secrets, and URL userinfo.

This is a bounded heuristic, **not** a DLP product: detection uses known patterns and sensitive key
names, never entropy alone, so ordinary identifiers (UUIDs, hashes, trace IDs, hostnames) are
preserved, and an unrecognized secret format is not detected. See
[Correctness and Safety Contracts](docs/evaluation/correctness-and-safety-contracts.md).

## Human Approval Binding

A human approval binds the execution-relevant content of the request: action type, target,
environment, parameters, and the resolved execution backend, profile identity, and profile
configuration. Explanation prose is excluded. Before any external dispatch the binding is
recomputed, and a mismatch blocks execution with an `APPROVAL_STALE` audit event. This binds the
approved request; it is not an IAM system and does not add roles, tenancy, or delegation.

## Execution Failure Classification

A dispatch that provably did not reach the remote system may be retried under bounded policy. A
dispatch whose outcome is ambiguous — a read or write failure, reset, timeout, ambiguous server
error, or a missing acceptance handle after submission — becomes `UNKNOWN` and is never retried;
it requires reconciliation. OpsPilot does not claim exactly-once delivery.

## Supported Versions

OpsPilot is pre-release software. Security fixes are applied to the latest `main` branch only;
no production-readiness claim is made.
