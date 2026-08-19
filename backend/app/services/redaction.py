from __future__ import annotations

import hashlib
import re
from typing import Any

SECRET_ASSIGNMENT = re.compile(
    r"(?i)\b(password|passwd|token|secret|credential|authorization|private[_-]?key)"
    r"\s*[:=]\s*([^\s,;]+)"
)
COMMAND_ASSIGNMENT = re.compile(r"(?i)\b(command|argv|args)\s*[:=]\s*([^\n]+)")
IPV4 = re.compile(r"(?<![\d.])(?:\d{1,3}\.){3}\d{1,3}(?![\d.])")


def _alias(prefix: str, value: str) -> str:
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()[:10]
    return f"{prefix}-{digest}"


def redact_hostname(value: str) -> str:
    if value.startswith("host-") and len(value) == 15:
        return value
    return _alias("host", value)


def redact_account(value: str) -> str:
    if value in {"worker", "system"}:
        return value
    if value.startswith("account-") and len(value) == 18:
        return value
    return _alias("account", value)


def redact_text(
    value: str | None,
    *,
    hostnames: tuple[str, ...] = (),
    accounts: tuple[str, ...] = (),
) -> str | None:
    if value is None:
        return None
    redacted = SECRET_ASSIGNMENT.sub(lambda match: f"{match.group(1)}=[REDACTED]", value)
    redacted = COMMAND_ASSIGNMENT.sub(
        lambda match: f"{match.group(1)}=[REDACTED_COMMAND]", redacted
    )
    redacted = IPV4.sub("[REDACTED_IP]", redacted)
    for hostname in sorted(set(hostnames), key=len, reverse=True):
        if hostname:
            redacted = redacted.replace(hostname, redact_hostname(hostname))
    for account in sorted(set(accounts), key=len, reverse=True):
        if account:
            redacted = redacted.replace(account, redact_account(account))
    return redacted


def redact_details(value: Any, key: str = "") -> Any:
    normalized = key.lower()
    if normalized in {"command", "argv", "args", "parameters", "command_parameters"}:
        return "[REDACTED_COMMAND]"
    if isinstance(value, dict):
        return {item_key: redact_details(item, str(item_key)) for item_key, item in value.items()}
    if isinstance(value, list):
        return [redact_details(item, key) for item in value]
    if isinstance(value, tuple):
        return [redact_details(item, key) for item in value]
    if isinstance(value, str):
        if normalized in {"host", "hostname", "hosts", "hostnames"}:
            return redact_hostname(value)
        if normalized in {
            "actor",
            "account",
            "accounts",
            "username",
            "requested_by",
            "approver",
        }:
            return redact_account(value)
        return redact_text(value)
    return value
