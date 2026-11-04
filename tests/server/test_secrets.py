"""architecture.md section 29.2 -- both directions matter: true positives,
and the false-positive exclusions (entropy, `password =`) stay excluded."""
from __future__ import annotations

import pytest

from copiq_server.application.secrets import scan

TRUE_POSITIVES = [
    "AKIAABCDEFGHIJKLMNOP",
    "ghp_" + "a" * 36,
    "github_pat_" + "a" * 22,
    "xoxb-" + "111111111-222222222-abcdefghijklmnop",
    "sk_live_" + "a" * 24,
    "AIza" + "a" * 35,
    "sk-ant-" + "a" * 20,
    "-----BEGIN RSA PRIVATE KEY-----",
    "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dozjgNryP4J3jVmNHl0w5N_XgL0n3I9PlFmbmMS7VpVL",
    "postgres://user:hunter2@db.internal:5432/app",
]


@pytest.mark.parametrize("content", TRUE_POSITIVES)
def test_flags_known_secret_shapes(content):
    result = scan(f"here is some text {content} more text")
    assert result.flagged, content


FALSE_POSITIVE_EXCLUSIONS = [
    "git commit abc123def456789012345678901234567890abcd",
    "password = get_password_from_vault()",
    "the quick brown fox jumps over the lazy dog",
    "a" * 200,  # high entropy-ish but not a recognized shape
]


@pytest.mark.parametrize("content", FALSE_POSITIVE_EXCLUSIONS)
def test_does_not_flag_ordinary_developer_text(content):
    result = scan(content)
    assert not result.flagged, content
