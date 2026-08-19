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

## Supported Versions

OpsPilot is pre-release software. Security fixes are applied to the latest `main` branch only;
no production-readiness claim is made.
