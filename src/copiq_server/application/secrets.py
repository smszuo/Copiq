"""Secret scanner -- architecture.md section 29.

Deliberately crude: a fixed list of high-confidence patterns only. No entropy
heuristics, no keying off variable names like `password =` -- both misfire
constantly on ordinary developer text (a base64 blob, a git SHA, a doc
example), and a false positive here blocks an action on content the user
copied deliberately.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("aws_access_key", re.compile(r"\b(AKIA|ASIA)[0-9A-Z]{16}\b")),
    ("github_token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{36,}\b|\bgithub_pat_[A-Za-z0-9_]{20,}\b")),
    ("slack_token", re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b")),
    ("stripe_key", re.compile(r"\b(sk|rk)_live_[A-Za-z0-9]{20,}\b")),
    ("google_api_key", re.compile(r"\bAIza[0-9A-Za-z_\-]{35}\b")),
    ("anthropic_or_openai_key", re.compile(r"\bsk-(ant-)?[A-Za-z0-9_-]{20,}\b")),
    ("private_key_pem", re.compile(r"-----BEGIN (RSA|EC|OPENSSH|PGP)? ?PRIVATE KEY-----")),
    ("jwt", re.compile(r"\beyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\b")),
    ("credential_in_url", re.compile(r"[a-zA-Z][a-zA-Z0-9+.\-]*://[^\s/:@]+:[^\s/@]+@")),
]


@dataclass(frozen=True)
class ScanResult:
    flagged: bool
    matched_pattern: str | None = None


def scan(content: str) -> ScanResult:
    for name, pattern in _PATTERNS:
        if pattern.search(content):
            return ScanResult(flagged=True, matched_pattern=name)
    return ScanResult(flagged=False)
