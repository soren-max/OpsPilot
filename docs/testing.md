# Testing Strategy

## Unit Tests

Domain model tests reject unknown actions, mismatched parameter schemas, unsafe identifiers, and
extra fields. Table-driven policy tests cover read-only, medium-risk, approval, and target rules.

## Integration Tests

Adapter tests verify fixed Action-to-Playbook mapping, generated variables, allowlists, and
post-action verification. Existing API, database, approval, and frontend tests protect the
deprecated migration baseline.

## Workflow Tests

Planned for the LangGraph milestone. They will verify state transitions, interrupts, checkpoint
resume behavior, and evidence-before-action routing.

## Security Tests

The current suite covers schema rejection, policy fail-closed behavior, output redaction, fixed
Ansible mappings, and the representative unsafe process-kill request. CI also runs a heuristic
secret scan and frontend dependency audit.

Future milestones add incident datasets, agent evaluation, adversarial safety evaluation, and
trace assertions.
