"""Small deterministic repository gate; use gitleaks additionally when available."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

PATTERNS = {
    "private key": re.compile(r"-----BEGIN (?:[A-Z0-9 ]+ )?PRIVATE KEY-----"),
    "AWS access key": re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    "GitHub token": re.compile(r"\bgh[pousr]_[A-Za-z0-9]{30,}\b"),
    "OpenAI-style token": re.compile(r"\bsk-[A-Za-z0-9_-]{24,}\b"),
}
ALLOWED_SUFFIXES = {
    ".py",
    ".ts",
    ".tsx",
    ".js",
    ".mjs",
    ".json",
    ".md",
    ".yml",
    ".yaml",
    ".toml",
    ".sh",
    ".env",
    ".example",
}


def tracked_files() -> list[Path]:
    output = subprocess.check_output(["git", "ls-files", "-co", "--exclude-standard"], text=True)
    return [Path(line) for line in output.splitlines() if line]


def main() -> int:
    findings: list[tuple[Path, str]] = []
    for path in tracked_files():
        if not path.is_file() or path.suffix not in ALLOWED_SUFFIXES:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for label, pattern in PATTERNS.items():
            if path.name == "check-secrets.py":
                continue
            if pattern.search(text):
                findings.append((path, label))
    if findings:
        for path, label in findings:
            print(f"potential {label}: {path}")
        return 1
    print("heuristic secret scan passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
