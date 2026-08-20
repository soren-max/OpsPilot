class CapabilityError(Exception):
    code = "CAPABILITY_ERROR"


class CapabilityUnavailable(CapabilityError):
    code = "CAPABILITY_UNAVAILABLE"


class CapabilityTimeout(CapabilityError):
    code = "CAPABILITY_TIMEOUT"


class CapabilityQueryRejected(CapabilityError):
    code = "CAPABILITY_QUERY_REJECTED"


class CapabilityMalformedResponse(CapabilityError):
    code = "CAPABILITY_MALFORMED_RESPONSE"
