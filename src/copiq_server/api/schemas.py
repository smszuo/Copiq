"""Pydantic wire schemas -- the validating authority (architecture.md 9.1).

Field names are camelCase on the wire; the shapes here must keep the same
key set as copiq_shared.types -- see tests/server/test_wire_contracts.py.
"""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel


class Wire(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class CreateClipboardRequest(Wire):
    content: str
    source: str
    client_id: str
    content_type: str = "text/plain"


class CreateClipboardResponse(Wire):
    id: int
    created_at: str
    deduplicated: bool


class ClipboardItemOut(Wire):
    id: int
    content: str
    content_type: str
    source: str
    client_id: str
    has_possible_secret: bool
    created_at: str


class ListResponse(Wire):
    items: list[ClipboardItemOut]
    next_cursor: int | None = None
    has_more: bool


class ActionRequest(Wire):
    action: str
    parameters: dict[str, str] | None = None
    acknowledge_secret: bool = False


class ActionResponse(Wire):
    clipboard_item_id: int
    action: str
    parameters: dict[str, str]
    status: str
    result: str | None = None
    error_message: str | None = None
    cached: bool
