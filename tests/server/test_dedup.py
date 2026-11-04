"""architecture.md section 13 -- content_hash + section 13.1 dedup rules."""
from __future__ import annotations

from copiq_server.application.hashing import content_hash


def test_content_hash_is_deterministic():
    assert content_hash("hello") == content_hash("hello")


def test_content_hash_differs_for_different_content():
    assert content_hash("hello") != content_hash("hello!")


def test_content_hash_is_sha256_hex():
    h = content_hash("hello")
    assert len(h) == 64
    int(h, 16)  # raises if not valid hex
