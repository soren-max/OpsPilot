import re
from dataclasses import dataclass

SENSITIVE_OUTPUT = (
    re.compile(r"(?i)(password|passwd|token|secret)\s*[:=]\s*([^\s,;]+)"),
    re.compile(r"(?i)(authorization\s*:\s*bearer)\s+([^\s]+)"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----", re.DOTALL),
)


def redact_sensitive_output(value: str) -> str:
    redacted = value
    redacted = SENSITIVE_OUTPUT[0].sub(r"\1=[REDACTED]", redacted)
    redacted = SENSITIVE_OUTPUT[1].sub(r"\1 [REDACTED]", redacted)
    redacted = SENSITIVE_OUTPUT[2].sub("[REDACTED PRIVATE KEY]", redacted)
    return redacted


@dataclass(frozen=True)
class ParsedOutput:
    state: str
    parse_success: bool
    message: str
    raw_stdout: str
    raw_stderr: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "raw_stdout", redact_sensitive_output(self.raw_stdout))
        object.__setattr__(self, "raw_stderr", redact_sensitive_output(self.raw_stderr))
