class McpCapabilityError(RuntimeError):
    code = "MCP_CAPABILITY_ERROR"


class McpUnavailable(McpCapabilityError):
    code = "MCP_UNAVAILABLE"


class McpTimeout(McpCapabilityError):
    code = "MCP_TIMEOUT"


class McpUnauthorized(McpCapabilityError):
    code = "MCP_UNAUTHORIZED"


class McpProtocolError(McpCapabilityError):
    code = "MCP_PROTOCOL_ERROR"


class McpMalformedResult(McpCapabilityError):
    code = "MCP_MALFORMED_RESULT"
