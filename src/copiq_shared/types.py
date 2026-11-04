"""Wire-shape contracts safe for the CLI to import.

TypedDict only -- no Pydantic here. Pydantic costs the CLI ~32ms of startup
for validation it does not need (see architecture.md section 9.1); TypedDict
is erased at runtime and costs ~3ms.

The server's Pydantic models in copiq_server/api/schemas.py are the
validating authority. tests/server/test_wire_contracts.py asserts the two
stay in sync -- if that test gets hard to write, the shapes have genuinely
diverged and this split should be collapsed.
"""
from __future__ import annotations

from typing import NotRequired, TypedDict


class ClipboardItemOut(TypedDict):
    id: int
    content: str
    contentType: str
    source: str
    clientId: str
    hasPossibleSecret: bool
    createdAt: str


class CreateClipboardResponse(TypedDict):
    id: int
    createdAt: str
    deduplicated: bool


class ListResponse(TypedDict):
    items: list[ClipboardItemOut]
    nextCursor: NotRequired[int | None]
    hasMore: bool


class ActionResponse(TypedDict):
    clipboardItemId: int
    action: str
    parameters: dict
    status: str
    result: NotRequired[str | None]
    errorMessage: NotRequired[str | None]
    cached: bool
