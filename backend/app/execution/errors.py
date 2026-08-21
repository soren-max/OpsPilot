class ExecutionPlaneError(RuntimeError):
    pass


class IndeterminateDispatch(ExecutionPlaneError):
    """The external system may have accepted the side effect; dispatch must not retry."""


class BackendUnavailable(ExecutionPlaneError):
    pass


class MalformedBackendResponse(ExecutionPlaneError):
    pass
