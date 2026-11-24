"""OpenAI provider -- architecture.md section 17 ("OpenAiProvider").

Calls the OpenAI Responses API over plain httpx (already a dependency), so
no SDK is added. The API key comes from the OPENAI_API_KEY env var, never
from copiq.toml, so it can't end up in a committed config file.

`store: false` keeps OpenAI from retaining the response on its side --
clipboard content is untrusted and possibly sensitive.
"""
from __future__ import annotations

import asyncio
import time

import httpx

from copiq_server.providers.base import PROMPT_TEMPLATE, AiProviderError, AiRequest, AiResult

_RESPONSES_URL = "https://api.openai.com/v1/responses"


class OpenAiProvider:  # satisfies AiProvider structurally
    def __init__(
        self,
        *,
        api_key: str | None,
        model: str = "gpt-6-luna",
        timeout_seconds: int = 120,
        transport: httpx.AsyncBaseTransport | None = None,  # tests inject httpx.MockTransport
    ) -> None:
        self._api_key = api_key
        self._model = model
        self._timeout_seconds = timeout_seconds
        self._transport = transport

    async def execute(self, request: AiRequest) -> AiResult:
        if not self._api_key:
            raise AiProviderError("OPENAI_API_KEY is not set")

        model = request.model or self._model
        body = {
            "model": model,
            "input": PROMPT_TEMPLATE.format(instruction=request.prompt, content=request.input),
            "store": False,
        }

        started = time.monotonic()
        try:
            # asyncio.timeout bounds the whole call; httpx's own timeout is per phase.
            async with (
                asyncio.timeout(self._timeout_seconds),
                httpx.AsyncClient(timeout=self._timeout_seconds, transport=self._transport) as client,
            ):
                resp = await client.post(
                    _RESPONSES_URL,
                    json=body,
                    headers={"Authorization": f"Bearer {self._api_key}"},
                )
        except (TimeoutError, httpx.TimeoutException):
            raise AiProviderError(f"OpenAI API timed out after {self._timeout_seconds}s") from None
        except httpx.HTTPError as e:
            raise AiProviderError(f"OpenAI API request failed: {e}") from e
        duration_ms = int((time.monotonic() - started) * 1000)

        if resp.status_code != 200:
            raise AiProviderError(f"OpenAI API returned {resp.status_code}: {resp.text[:2000]}")

        try:
            data = resp.json()
        except ValueError as e:
            raise AiProviderError(f"OpenAI API produced non-JSON output: {e}") from e

        # A proxy can answer 200 with any JSON ([], null, ...); that must fail
        # as AiProviderError, not escape as an AttributeError (HTTP 500).
        try:
            if data.get("status") != "completed":
                detail = data.get("error") or data.get("incomplete_details")
                raise AiProviderError(f"OpenAI response status {data.get('status')!r}: {detail!r}")

            text = "".join(
                part.get("text", "")
                for item in data.get("output") or []
                if item.get("type") == "message"
                for part in item.get("content") or []
                if part.get("type") == "output_text"
            )
            usage = data.get("usage") or {}
        except (AttributeError, TypeError) as e:
            raise AiProviderError(f"OpenAI API returned an unexpected response shape: {e}") from e

        # An empty or refused answer must fail, not be cached as "completed".
        if not text:
            raise AiProviderError(f"OpenAI returned no text output: {data.get('output')!r}"[:2000])

        return AiResult(
            content=text,
            model=data.get("model", model),
            provider_version="openai-responses",
            input_tokens=usage.get("input_tokens"),
            output_tokens=usage.get("output_tokens"),
            duration_ms=duration_ms,
        )
