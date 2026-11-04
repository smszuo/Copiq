"""AI actions endpoint -- architecture.md section 15."""
from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from copiq_server.api.schemas import ActionRequest, ActionResponse
from copiq_server.application.pipeline import PipelineError, run_action
from copiq_server.auth import require_api_key
from copiq_server.deps import get_ai_provider, get_db, get_settings_dep
from copiq_server.domain.models import ApiKey, ClipboardItem

router = APIRouter(prefix="/api/clipboard", tags=["actions"])

_auth = require_api_key(get_db)


@router.post("/{item_id}/actions", response_model=ActionResponse)
async def run_clipboard_action(
    item_id: int,
    body: ActionRequest,
    db: Session = Depends(get_db),
    settings=Depends(get_settings_dep),
    provider=Depends(get_ai_provider),
    _key: ApiKey = Depends(_auth),
) -> ActionResponse:
    item = db.get(ClipboardItem, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="clipboard item not found")

    try:
        outcome = await run_action(
            db,
            item=item,
            action_name=body.action,
            parameters=body.parameters,
            acknowledge_secret=body.acknowledge_secret,
            provider=provider,
            provider_name=settings.ai.provider,
            settings=settings,
        )
    except PipelineError as e:
        raise HTTPException(status_code=e.status_code, detail=str(e)) from e

    row = outcome.result
    return ActionResponse(
        clipboard_item_id=row.clipboard_item_id,
        action=row.action,
        parameters=json.loads(row.parameters) if row.parameters else {},
        status=row.status,
        result=row.result,
        error_message=row.error_message,
        cached=outcome.cached,
    )
