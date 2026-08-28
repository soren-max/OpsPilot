# ADR 0013: SSH Is an Infrastructure Detail

## Status

Accepted.

## Decision

OpsPilot may use SSH only through its infrastructure-owned Ansible adapter. Action requests,
Policy, Workflow, LLM and MCP contracts express semantic service actions and cannot specify host,
user, credential, inventory, remote path, argv or shell syntax.

## Consequences

Traditional SSH-managed environments remain integrable without restoring `ServiceSSH` or an
arbitrary remote-command API. Deployment operators own connectivity configuration and credentials;
application behavior stays transport-independent and architecture tests enforce the boundary.
