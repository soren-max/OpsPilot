# Legacy Environment Migration Guide

This guide uses the synthetic `legacy-host` lab to show a minimal-remediation migration path for an
SSH-managed test environment. It is not a production deployment guide and contains no real company
hostnames, addresses, users, services, tickets or credentials.

## 1. Assess before integrating

Copy `deployment/templates/private-deployment.yaml` into a private configuration repository. Map
semantic services to operator-owned inventory, service-control and verification profile refs. Keep
credential material in a secret file, CI secret or secret provider and expose only its environment
reference to OpsPilot.

```bash
make migration-assess PROFILE=example-legacy-test
make deployment-preview PROFILE=example-legacy-test
```

Preview must show `RESTART_SERVICE`, Ansible, the control type, verification type and approval
requirement. It intentionally omits the hostname, user, key, token and full command.

## 2. Run the read-only doctor

```bash
export OPSPILOT_LEGACY_SSH_KEY_FILE=/path/from/your/secret/provider
make deployment-doctor PROFILE=/private/config/deployment.yaml
```

Resolve failed checks without letting OpsPilot modify the server. A missing package, port or agent
is a deployment-owner concern; doctor does not install or reconfigure anything.

## 3. Select a bounded control mode

For systemd, map semantic service names to exact unit names. For a legacy service script, map to one
fixed absolute script path and exact script service IDs. Only status/start/stop/restart enum values
are accepted. Do not create a raw SSH, command, path, args or key endpoint.

## 4. Require verification

Define current-state checks independently of execution. At least one required check must exist.
Prefer HTTP health plus service/process state where available. Endpoint and success criteria are
operator-owned configuration, never LLM output.

## 5. Migrate incrementally

The compatibility API accepts only incident/evidence-bound restart proposals. It enters the normal
Policy and durable HITL workflow and returns an approval reference; it cannot execute immediately.
Unsafe legacy request shapes require migration instead of being passed through.

## Synthetic E2E

```bash
make legacy-demo
make legacy-down
```

The demo proves Incident → Evidence → Diagnosis → Policy → Approval → ExecutionRouter → Ansible →
SSH → fixed script → Verification → RESOLVED. The private key is generated into an ephemeral Docker
volume at runtime and is never committed.
