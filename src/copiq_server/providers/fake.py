"""FakeAiProvider -- architecture.md section 33. Prevents tests from making
real AI requests, and its call log is what makes the cache testable."""
from __future__ import annotations

from copiq_server.providers.base import AiRequest, AiResult


class FakeAiProvider:
    def __init__(self, responses: dict[str, str] | None = None, *, default: str = "faked") -> None:
        self.responses = responses or {}
        self.default = default
        self.calls: list[AiRequest] = []

    async def execute(self, request: AiRequest) -> AiResult:
        self.calls.append(request)
        content = self.responses.get(request.input, self.default)
        return AiResult(
            content=content,
            model="fake",
            provider_version="fake/1",
            input_tokens=1,
            output_tokens=1,
            duration_ms=0,
        )
