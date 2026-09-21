from __future__ import annotations

import hashlib
import re
from typing import Any

# Ordered deliberately: structural secrets are consumed before generic key=value rules.
PRIVATE_KEY_BLOCK = re.compile(
    r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----.*?-----END [A-Z0-9 ]*PRIVATE KEY-----",
    re.DOTALL,
)
AUTHORIZATION_HEADER = re.compile(
    r"(?i)\b(?:proxy-)?authorization\b\s*[:=]\s*(?:bearer|basic|token)?\s*[A-Za-z0-9._~+/=\-]{4,}"
)
JWT = re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\b")
SECRET_ASSIGNMENT = re.compile(
    r"(?i)\b(password|passwd|pwd|token|secret|credential|credentials|"
    r"api[_-]?key|apikey|access[_-]?key|secret[_-]?key|private[_-]?key|"
    r"client[_-]?secret|webhook[_-]?secret|auth[_-]?token|bearer)"
    r"[\"']?\s*[:=]\s*[\"']?([^\s,;}\"']+)"
)
URL_CREDENTIALS = re.compile(
    r"(?i)\b([a-z][a-z0-9+.\-]*://)([^/\s:@]+):([^/\s@]+)@"
)
CLOUD_ACCESS_KEY = re.compile(r"\b(?:AKIA|ASIA|ABIA|ACCA)[0-9A-Z]{16}\b")
SLACK_TOKEN = re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b")
SLACK_WEBHOOK = re.compile(r"https://hooks\.slack\.com/services/\S+")
COMMAND_ASSIGNMENT = re.compile(r"(?i)\b(command|argv|args)\s*[:=]\s*([^\n]+)")
IPV4 = re.compile(r"(?<![\d.])(?:\d{1,3}\.){3}\d{1,3}(?![\d.])")

# Sensitive key names whose whole value is withheld rather than pattern-matched.
SENSITIVE_KEYS = frozenset(
    {
        "token",
        "secret",
        "password",
        "passwd",
        "pwd",
        "credential",
        "credentials",
        "api_key",
        "apikey",
        "access_key",
        "secret_key",
        "private_key",
        "authorization",
        "auth_token",
        "client_secret",
        "webhook_secret",
        "bearer",
        "dsn",
        "connection_string",
        "database_url",
    }
)


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
    """Remove known credential shapes. Never relies on entropy alone, so UUIDs,
    content hashes, trace IDs and ordinary hostnames survive unchanged."""

    if value is None:
        return None
    redacted = PRIVATE_KEY_BLOCK.sub("[REDACTED_PRIVATE_KEY]", value)
    redacted = AUTHORIZATION_HEADER.sub("authorization=[REDACTED]", redacted)
    redacted = JWT.sub("[REDACTED_JWT]", redacted)
    redacted = SECRET_ASSIGNMENT.sub(lambda match: f"{match.group(1)}=[REDACTED]", redacted)
    redacted = URL_CREDENTIALS.sub(lambda match: f"{match.group(1)}[REDACTED]@", redacted)
    redacted = CLOUD_ACCESS_KEY.sub("[REDACTED_ACCESS_KEY]", redacted)
    redacted = SLACK_TOKEN.sub("[REDACTED_WEBHOOK_SECRET]", redacted)
    redacted = SLACK_WEBHOOK.sub("[REDACTED_WEBHOOK_URL]", redacted)
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

    def withheld(item: Any) -> Any:
        if isinstance(item, dict):
            return {nested: withheld(inner) for nested, inner in item.items()}
        if isinstance(item, (list, tuple)):
            return [withheld(entry) for entry in item]
        if isinstance(item, str):
            return "[REDACTED]"
        return item

    if normalized in SENSITIVE_KEYS:
        return withheld(value)
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


def sanitize_text(value: str | None, *, limit: int) -> str | None:
    """Redact then re-bound, because redaction placeholders can lengthen a value."""

    redacted = redact_text(value)
    if redacted is None:
        return None
    return redacted[:limit]


def sanitize_metadata(value: dict[str, Any]) -> dict[str, Any]:
    sanitized = redact_details(value)
    return sanitized if isinstance(sanitized, dict) else {}


_REDACTION_RULES: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("private_key", PRIVATE_KEY_BLOCK),
    ("authorization_header", AUTHORIZATION_HEADER),
    ("jwt", JWT),
    ("secret_assignment", SECRET_ASSIGNMENT),
    ("url_credentials", URL_CREDENTIALS),
    ("cloud_access_key", CLOUD_ACCESS_KEY),
    ("webhook_secret", SLACK_TOKEN),
    ("webhook_url", SLACK_WEBHOOK),
)


def redaction_summary(value: str | None) -> dict[str, int]:
    """Report credential shapes by kind and count. Never returns secret content."""

    if not value:
        return {}
    summary: dict[str, int] = {}
    for name, pattern in _REDACTION_RULES:
        found = len(pattern.findall(value))
        if found:
            summary[name] = found
    return summary