class ExecutionPlaneError(RuntimeError):
    pass


class IndeterminateDispatch(ExecutionPlaneError):
    """The request may have reached the remote system; dispatch must never retry.

    Raised when the failure happened after the request was written to the connection but no
    usable acceptance handle was observed: a read timeout, a reset while reading the response,
    a malformed acceptance response, or a worker crash between intent and confirmation.
    """


class BackendUnavailable(ExecutionPlaneError):
    """The request provably did not reach the remote system, so a bounded retry is safe."""


class MalformedBackendResponse(ExecutionPlaneError):
    pass
