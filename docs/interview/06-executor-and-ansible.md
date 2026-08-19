# Executor and Ansible

Status: **Implemented**

## Concept

An executor port isolates domain actions from infrastructure transports.

## Where in OpsPilot

`ActionExecutor`, `MockActionExecutor`, `AnsibleActionExecutor`, and fixed Playbooks.

## Why

The domain should not know SSH, subprocess syntax, inventory paths, or Ansible internals.

## Trade-offs

Fixed mappings reduce flexibility and require a code review for every executable capability.

## Failure Modes

Path escape, target bypass, unsafe variables, timeout, partial failure, and false verification.

## Interview Questions

- Why apply allowlists in both policy and adapter layers?
- Why is `create_subprocess_exec` preferable to a shell command?
