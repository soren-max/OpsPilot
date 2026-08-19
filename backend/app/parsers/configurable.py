from __future__ import annotations

import re

from app.core.command_profiles import OutputParserConfig, load_custom_parser
from app.parsers.base import StatusOutputParser
from app.parsers.json_status import JsonStatusParser
from app.parsers.legacy_text_status import LegacyTextStatusParser
from app.parsers.raw_output import RawOutputParser
from app.parsers.status_result import ParsedOutput


class DeclarativeRegexParser:
    def __init__(self, config: OutputParserConfig) -> None:
        self.config = config

    def parse(self, stdout: str, stderr: str, exit_code: int) -> ParsedOutput:
        matches: list[str] = []
        for state, pattern in self.config.stdout_regex.items():
            if re.search(pattern, stdout, re.MULTILINE):
                matches.append(state)
        for state, pattern in self.config.stderr_regex.items():
            if re.search(pattern, stderr, re.MULTILINE):
                matches.append(state)
        mapped = self.config.exit_code_map.get(exit_code)
        if mapped:
            matches.append(mapped)
        unique = list(dict.fromkeys(matches))
        if len(unique) > 1 and self.config.conflict_policy == "failed":
            state = "failed"
            success = False
            message = "Conflicting output rules matched: " + ", ".join(unique)
        elif unique:
            state = unique[-1] if self.config.conflict_policy == "last" else unique[0]
            success = state != "parse_failed"
            message = f"Declarative parser selected {state}"
        else:
            state = self.config.default_state
            success = state != "parse_failed"
            message = f"Declarative parser used default {state}"
        return ParsedOutput(state, success, message, stdout, stderr)


class ExitCodeMappedParser:
    def __init__(self, parser: StatusOutputParser, config: OutputParserConfig) -> None:
        self.parser = parser
        self.config = config

    def parse(self, stdout: str, stderr: str, exit_code: int) -> ParsedOutput:
        parsed = self.parser.parse(stdout, stderr, exit_code)
        mapped = self.config.exit_code_map.get(exit_code)
        if mapped is None:
            return parsed
        return ParsedOutput(
            state=mapped,
            parse_success=mapped != "parse_failed",
            message=f"exit_code_map selected {mapped}",
            raw_stdout=parsed.raw_stdout,
            raw_stderr=parsed.raw_stderr,
        )


def build_status_parser(config: OutputParserConfig) -> StatusOutputParser:
    if config.type == "json":
        parser: StatusOutputParser = JsonStatusParser()
        return ExitCodeMappedParser(parser, config)
    if config.type == "regex":
        return DeclarativeRegexParser(config)
    if config.type == "legacy_text":
        parser = LegacyTextStatusParser()
        return ExitCodeMappedParser(parser, config)
    if config.type == "raw":
        parser = RawOutputParser()
        return ExitCodeMappedParser(parser, config)
    assert config.custom_parser is not None
    parser = load_custom_parser(config.custom_parser)
    return ExitCodeMappedParser(parser, config)
