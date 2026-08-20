class LLMFailure(Exception):
    code = "LLM_FAILURE"
    retryable = False


class LLMUnavailable(LLMFailure):
    code = "LLM_UNAVAILABLE"
    retryable = True


class LLMTimeout(LLMFailure):
    code = "LLM_TIMEOUT"
    retryable = True


class LLMRateLimited(LLMFailure):
    code = "LLM_RATE_LIMITED"
    retryable = True


class LLMMalformedOutput(LLMFailure):
    code = "LLM_MALFORMED_OUTPUT"


class LLMGroundingFailure(LLMFailure):
    code = "LLM_GROUNDING_FAILURE"


class LLMPolicyViolation(LLMFailure):
    code = "LLM_POLICY_VIOLATION"
