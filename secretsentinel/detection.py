"""Secret detection without persistence or network calls."""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SecretMatch:
    kind: str
    start: int
    end: int


PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("Discord bot token", re.compile(r"(?<![\w-])(?:mfa\.[\w-]{40,}|[A-Za-z\d_-]{23,28}\.[A-Za-z\d_-]{6}\.[A-Za-z\d_-]{27,})")),
    (
        "Discord webhook URL",
        re.compile(r"https://(?:canary\.|ptb\.)?discord(?:app)?\.com/api/webhooks/\d{17,20}/[A-Za-z\d_-]{40,}"),
    ),
    ("GitHub token", re.compile(r"(?<![A-Za-z\d_])(?:gh[pousr]_[A-Za-z\d]{36,255}|github_pat_[A-Za-z\d_]{70,255})")),
    ("AWS access key", re.compile(r"(?<![A-Z0-9])(?:AKIA|ASIA)[A-Z0-9]{16}(?![A-Z0-9])")),
    ("Google API key", re.compile(r"(?<![A-Za-z\d_-])AIza[A-Za-z\d_-]{35}(?![A-Za-z\d_-])")),
    ("Stripe live key", re.compile(r"(?<![A-Za-z\d_])(?:sk|rk)_live_[A-Za-z\d]{20,}(?![A-Za-z\d_])")),
    ("Private key", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----")),
)


def find_secrets(text: str) -> list[SecretMatch]:
    """Return non-overlapping secret locations without copying matched values."""
    matches = [SecretMatch(kind, match.start(), match.end()) for kind, pattern in PATTERNS for match in pattern.finditer(text)]
    matches.sort(key=lambda item: (item.start, -(item.end - item.start)))
    accepted: list[SecretMatch] = []
    for item in matches:
        if not accepted or item.start >= accepted[-1].end:
            accepted.append(item)
    return accepted


def redact(text: str, matches: list[SecretMatch] | None = None) -> str:
    """Replace detected values while preserving the surrounding diagnostic text."""
    matches = matches if matches is not None else find_secrets(text)
    for item in reversed(matches):
        text = f"{text[: item.start]}[REDACTED {item.kind}]{text[item.end :]}"
    return text
