# Governed Execution (Future Design)

This is design only. M1B adds no production implementation or unused interface.

## Responsibility split

- **OpsPilot:** investigation, evidence, proposal, Target context, and risk context.
- **Policy:** deterministic authorization and approval requirements.
- **Harness:** possible future governed workflow execution for complex change.
- **GitOps:** possible future reconciliation path for deployment and configuration state.

## Candidate backend contract

```text
submit(governed_change) -> workflow_reference
get_status(workflow_reference) -> workflow_status
cancel(workflow_reference) -> cancellation_result
verify(workflow_reference, expected_outcome) -> verification_result
```

The submitted object must be structured and policy-authorized and must not contain a shell command
or user-selected backend detail. Polling and cancellation must be idempotent; verification remains
explicit and auditable.

## M1B non-goals

No Harness SDK, fake Harness adapter, generic executor factory, deployment action, rollback
action, or GitOps mutation endpoint is introduced.
