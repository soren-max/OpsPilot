class WorkflowFailure(RuntimeError):
    code = "WORKFLOW_FAILURE"
    retryable = False


class DomainFailure(WorkflowFailure):
    code = "DOMAIN_FAILURE"


class PolicyBlocked(WorkflowFailure):
    code = "POLICY_BLOCKED"


class ExecutionFailure(WorkflowFailure):
    code = "EXECUTION_FAILURE"


class VerificationFailure(WorkflowFailure):
    code = "VERIFICATION_FAILURE"


class WorkflowInfrastructureFailure(WorkflowFailure):
    code = "WORKFLOW_INFRASTRUCTURE_FAILURE"
    retryable = True
