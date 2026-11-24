"""OpenAiProvider against a mocked Responses API -- no real network calls."""
from __future__ import annotations

import json

import httpx
import pytest

from copiq_server.config import AiSettings
from copiq_server.providers.base import AiProviderError, AiRequest
from copiq_server.providers.openai_api import OpenAiProvider


def _provider(handler, api_key="sk-test"):
    return OpenAiProvider(api_key=api_key, transport=httpx.MockTransport(handler))


REQUEST = AiRequest(prompt="Translate.", input="hello")


async def test_parses_output_text_and_sends_expected_request():
    seen = {}

    def handler(req: httpx.Request) -> httpx.Response:
        seen["auth"] = req.headers["authorization"]
        seen["body"] = json.loads(req.content)
        return httpx.Response(200, json={
            "status": "completed",
            "model": "gpt-6-luna-2026-10-01",
            "output": [
                {"type": "reasoning", "summary": []},
                {"type": "message", "content": [{"type": "output_text", "text": "你好"}]},
            ],
            "usage": {"input_tokens": 12, "output_tokens": 3},
        })

    result = await _provider(handler).execute(REQUEST)

    assert result.content == "你好"
    assert result.model == "gpt-6-luna-2026-10-01"
    assert (result.input_tokens, result.output_tokens) == (12, 3)
    assert seen["auth"] == "Bearer sk-test"
    assert seen["body"]["model"] == "gpt-6-luna"
    assert seen["body"]["store"] is False
    assert "<<<TEXT\nhello\nTEXT>>>" in seen["body"]["input"]


@pytest.mark.parametrize("response", [
    httpx.Response(200, json=[]),
    httpx.Response(200, json={"status": "completed", "output": "not-a-list"}),
    httpx.Response(401, json={"error": {"message": "bad key"}}),
    httpx.Response(200, json={"status": "incomplete", "incomplete_details": {"reason": "max_output_tokens"}}),
    httpx.Response(200, json={"status": "completed", "output": [
        {"type": "message", "content": [{"type": "refusal", "refusal": "no"}]},
    ]}),
])
async def test_failures_raise_provider_error(response):
    with pytest.raises(AiProviderError):
        await _provider(lambda req: response).execute(REQUEST)


async def test_missing_api_key_fails_without_a_request():
    def handler(req):
        raise AssertionError("must not call the API without a key")

    with pytest.raises(AiProviderError, match="OPENAI_API_KEY"):
        await _provider(handler, api_key=None).execute(REQUEST)


def test_model_defaults_follow_the_provider():
    assert AiSettings().model == "haiku"
    assert AiSettings(provider="openai").model == "gpt-6-luna"
    assert AiSettings(provider="openai", model="gpt-6").model == "gpt-6"
    assert AiSettings(provider="openai", model="").model == "gpt-6-luna"


def test_unknown_provider_is_rejected_at_startup():
    with pytest.raises(ValueError):
        AiSettings(provider="opneai")
