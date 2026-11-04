"""AiProvider abstraction -- architecture.md section 17."""
from __future__ import annotations

from decimal import Decimal
from typing import Protocol

from pydantic import BaseModel


class AiRequest(BaseModel):
    prompt: str
    input: str
    model: str | None = None


class AiResult(BaseModel):
    content: str
    model: str
    provider_version: str
    input_tokens: int | None = None
    output_tokens: int | None = None
    cost_usd: Decimal | None = None
    duration_ms: int


class AiProviderError(Exception):
    """Raised by a provider on failure; the pipeline stores it as status=failed."""


class AiProvider(Protocol):
    async def execute(self, request: AiRequest) -> AiResult: ...
