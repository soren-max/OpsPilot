from app.parsers.status_result import ParsedOutput


class RawOutputParser:
    """Preserve unconfirmed site output without inferring a healthy state."""

    def parse(self, stdout: str, stderr: str, exit_code: int) -> ParsedOutput:
        return ParsedOutput(
            state="failed" if exit_code != 0 else "unknown",
            parse_success=exit_code == 0,
            message=(
                "Command failed; raw output preserved"
                if exit_code != 0
                else "Raw output preserved; service state is unknown"
            ),
            raw_stdout=stdout,
            raw_stderr=stderr,
        )
