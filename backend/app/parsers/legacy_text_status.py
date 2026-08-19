import re

from app.parsers.status_result import ParsedOutput

STATE_FIELD = re.compile(
    r"(?:^|[;\s])(?:STATE|STATUS)\s*[:=]\s*"
    r"(running|stopped|unknown|unreachable|not[_ -]?found|failed|timeout)(?:$|[;\s])",
    re.IGNORECASE,
)
NOT_FOUND = re.compile(r"\bservice\b.*\bnot[ -]?found\b", re.IGNORECASE)
UNREACHABLE = re.compile(r"\b(unreachable|host unreachable)\b", re.IGNORECASE)


class LegacyTextStatusParser:
    def parse(self, stdout: str, stderr: str, exit_code: int) -> ParsedOutput:
        combined = "\n".join(item for item in (stdout, stderr) if item)
        match = STATE_FIELD.search(combined)
        if match:
            state = match.group(1).lower().replace(" ", "_").replace("-", "_")
        elif NOT_FOUND.search(combined):
            state = "not_found"
        elif UNREACHABLE.search(combined):
            state = "unreachable"
        elif exit_code != 0:
            state = "failed"
        else:
            return ParsedOutput(
                state="parse_failed",
                parse_success=False,
                message="Legacy status output could not be parsed",
                raw_stdout=stdout,
                raw_stderr=stderr,
            )
        if exit_code != 0 and state in {"running", "stopped", "unknown"}:
            state = "failed"
        return ParsedOutput(
            state=state,
            parse_success=True,
            message=combined.strip() or state,
            raw_stdout=stdout,
            raw_stderr=stderr,
        )
