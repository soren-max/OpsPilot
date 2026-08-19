# Architecture

## Status

Milestone 1A implements the Action Safety Core. The incident workflow and capability adapters
are planned and are not represented as completed features.

```text
Future Incident Workflow
          |
          v
    ActionRequest
          |
          v
 ActionPolicyEngine ----> blocked / approval required
          |
          v
   ActionService
          |
          v
 ActionExecutor port
       /      \
      v        v
    Mock     Ansible
```

## Boundaries

- `app/domain/actions` owns strict action, risk, result, and executor contracts.
- `app/application` orchestrates policy and an injected executor.
- `app/adapters` translates validated actions into infrastructure-specific calls.
- `ansible/playbooks` contains the only playbooks addressable by the new Ansible adapter.
- Legacy operation, SSH, and service-script code remains deprecated for regression migration.

The dependency direction is Domain → Application → Port ← Adapter. Domain and application code
do not import SSH, Ansible, subprocess, or legacy wrappers.

## Explicit State, Not Hidden Reasoning

Future workflows will store evidence, hypotheses, decision summaries, proposed actions, and risk
reasons. OpsPilot will not record or depend on a model's hidden chain-of-thought.
