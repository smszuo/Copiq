"""architecture.md section 9.1 -- copiq_shared.types (TypedDict, imported
by the CLI) and copiq_server.api.schemas (Pydantic, the validating
authority) must expose the same field names. If this test gets hard to
write, the two have genuinely diverged and the split should be collapsed.
"""
from __future__ import annotations

from typing import get_type_hints

from pydantic.alias_generators import to_camel

from copiq_server.api import schemas
from copiq_shared import types as shared_types

PAIRS = [
    (shared_types.ClipboardItemOut, schemas.ClipboardItemOut),
    (shared_types.CreateClipboardResponse, schemas.CreateClipboardResponse),
    (shared_types.ActionResponse, schemas.ActionResponse),
]


def _typeddict_keys(td) -> set[str]:
    """TypedDicts are already written as wire shapes (camelCase)."""
    return set(get_type_hints(td).keys())


def _model_wire_keys(model) -> set[str]:
    """Pydantic field names are snake_case Python identifiers; the wire
    shape is the camelCase alias each field serializes as."""
    return {field.alias or to_camel(name) for name, field in model.model_fields.items()}


def test_shapes_match():
    for td, model in PAIRS:
        assert _typeddict_keys(td) == _model_wire_keys(model), f"{td.__name__} vs {model.__name__}"


def test_list_response_matches():
    td_keys = _typeddict_keys(shared_types.ListResponse)
    model_keys = _model_wire_keys(schemas.ListResponse)
    assert td_keys == model_keys
