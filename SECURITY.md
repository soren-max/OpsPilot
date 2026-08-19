# Security Policy

## Reporting a Vulnerability

Do not open a public issue for a suspected vulnerability or leaked credential. Use GitHub's
private vulnerability reporting feature for this repository. Include affected versions,
reproduction steps, and impact without including live secrets or personal data.

## Security Boundaries

OpsPilot does not accept arbitrary shell actions. Infrastructure changes must be represented by
strict structured actions, assessed by deterministic policy, approved when required, and sent
to an allowlisted adapter. LLM output is never an authorization decision.

The legacy SSH integration is deprecated and scheduled for removal in Milestone 1B. It is not
used by the new Action Safety Core.

## Supported Versions

OpsPilot is pre-release software. Security fixes are applied to the latest `main` branch only;
no production-readiness claim is made.
