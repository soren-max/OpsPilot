# ADR 0003: Ansible as Infrastructure Execution Adapter

## Status

Accepted

## Context

OpsPilot needs a reproducible execution layer without exposing transport details to its domain.

## Decision

Map ActionType values to application-owned Ansible Playbooks. Inventory and playbook paths are
constructor configuration, targets are allowlisted, variables come only from validated schemas,
and subprocess execution does not invoke a shell.

## Consequences

Actions require maintained Playbooks and Ansible availability. The domain remains replaceable by
future Docker or Kubernetes adapters.

## Alternatives Considered

Direct SSH, model-selected Playbooks, caller-supplied extra variables, and arbitrary commands were
rejected. `ansible-runner` remains a possible internal implementation detail.
