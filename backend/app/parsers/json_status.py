import json

from app.parsers.status_result import ParsedOutput

VALID_STATES = {
    "running",
    "stopped",
    "unknown",
    "unreachable",
    "not_found",
    "failed",
    "timeout",
}


class JsonStatusParser:
    def parse(self, stdout: str, stderr: str, exit_code: int) -> ParsedOutput:
        try:
            payload = json.loads(stdout)
            state = str(payload["state"]).lower()
            if state not in VALID_STATES:
                raise ValueError("unsupported state")
            message = str(payload.get("message") or state)
        except (json.JSONDecodeError, KeyError, TypeError, ValueError):
            return ParsedOutput(
                state="parse_failed",
                parse_success=False,
                message="JSON status output could not be parsed",
                raw_stdout=stdout,
                raw_stderr=stderr,
            )
        if exit_code != 0 and state not in {"unreachable", "not_found", "failed", "timeout"}:
            state = "failed"
        return ParsedOutput(state, True, message, stdout, stderr)
