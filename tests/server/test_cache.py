"""architecture.md section 22 -- every input that changes the output must be
in the cache key."""
from __future__ import annotations

from copiq_server.application.cache import compute_cache_key

BASE = dict(
    action="translate",
    normalized_parameters={"targetlanguage": "zh-cn"},
    content_hash="abc123",
    prompt_version="v1",
    provider="claude_cli",
    model="claude-haiku-4-5",
)


def test_same_inputs_same_key():
    assert compute_cache_key(**BASE) == compute_cache_key(**BASE)


def test_different_model_different_key():
    other = dict(BASE, model="claude-sonnet-5")
    assert compute_cache_key(**BASE) != compute_cache_key(**other)


def test_different_parameters_different_key():
    other = dict(BASE, normalized_parameters={"targetlanguage": "ja-jp"})
    assert compute_cache_key(**BASE) != compute_cache_key(**other)


def test_different_action_different_key():
    other = dict(BASE, action="explain")
    assert compute_cache_key(**BASE) != compute_cache_key(**other)


def test_different_provider_different_key():
    other = dict(BASE, provider="anthropic_api")
    assert compute_cache_key(**BASE) != compute_cache_key(**other)
