import json
from pathlib import Path

import pytest

from app.core.command_profiles import OutputParserConfig
from app.parsers import JsonStatusParser, LegacyTextStatusParser, RawOutputParser
from app.parsers.configurable import build_status_parser

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.mark.parametrize(
    ("stdout", "stderr", "exit_code", "state"),
    [
        ('{"state":"running"}', "", 0, "running"),
        ('{"state":"stopped"}', "", 0, "stopped"),
        ('{"state":"unknown"}', "", 0, "unknown"),
        ('{"state":"not_found"}', "", 5, "not_found"),
        ('{"state":"unreachable"}', "", 4, "unreachable"),
        ('{"state":"failed"}', "ansible failed", 2, "failed"),
        ('{"state":"timeout"}', "", 124, "timeout"),
        ('{"state":"running"}', "warning", 0, "running"),
    ],
)
def test_json_status_fixtures(stdout: str, stderr: str, exit_code: int, state: str) -> None:
    parsed = JsonStatusParser().parse(stdout, stderr, exit_code)
    assert parsed.state == state
    assert parsed.raw_stdout == stdout
    assert parsed.raw_stderr == stderr


@pytest.mark.parametrize(
    ("stdout", "stderr", "exit_code", "state", "success"),
    [
        ("STATE=running", "", 0, "running", True),
        ("STATUS: stopped", "", 0, "stopped", True),
        ("service redacted not found", "", 5, "not_found", True),
        ("", "host unreachable", 4, "unreachable", True),
        ("", "", 0, "parse_failed", False),
        ("opaque output", "", 0, "parse_failed", False),
        ("STATE=running", "fatal warning", 3, "failed", True),
    ],
)
def test_legacy_text_fixtures(
    stdout: str, stderr: str, exit_code: int, state: str, success: bool
) -> None:
    parsed = LegacyTextStatusParser().parse(stdout, stderr, exit_code)
    assert parsed.state == state
    assert parsed.parse_success is success
    assert parsed.raw_stdout == stdout
    assert parsed.raw_stderr == stderr


def test_raw_parser_never_guesses_running() -> None:
    assert RawOutputParser().parse("running-ish", "", 0).state == "unknown"
    assert RawOutputParser().parse("", "failed", 2).state == "failed"


def test_exit_code_map_overrides_structured_state() -> None:
    parser = build_status_parser(
        OutputParserConfig(
            type="json",
            exit_code_map={4: "unreachable", 124: "timeout"},
        )
    )
    assert parser.parse('{"state":"failed"}', "", 4).state == "unreachable"
    assert parser.parse('{"state":"running"}', "", 124).state == "timeout"


def test_parser_raw_diagnostics_redact_common_secret_shapes() -> None:
    parsed = RawOutputParser().parse(
        "token=do-not-store Authorization: Bearer opaque-value",
        "password: sensitive-value",
        0,
    )
    assert "do-not-store" not in parsed.raw_stdout
    assert "opaque-value" not in parsed.raw_stdout
    assert "sensitive-value" not in parsed.raw_stderr
    assert parsed.raw_stdout.count("[REDACTED]") == 2


def test_redacted_output_fixture_matrix() -> None:
    cases = json.loads((FIXTURES / "status_output_cases.json").read_text(encoding="utf-8"))
    parsers = {
        "json": JsonStatusParser(),
        "legacy": LegacyTextStatusParser(),
        "raw": RawOutputParser(),
    }
    for case in cases:
        parsed = parsers[case["parser"]].parse(case["stdout"], case["stderr"], case["exit_code"])
        assert parsed.state == case["state"], case["name"]
        assert parsed.parse_success is case["parse_success"], case["name"]
        assert parsed.raw_stdout == case["stdout"], case["name"]
        assert parsed.raw_stderr == case["stderr"], case["name"]
