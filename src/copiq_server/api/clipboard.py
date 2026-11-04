"""Clipboard endpoints -- architecture.md section 14."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from copiq_server.api.schemas import (
    ClipboardItemOut,
    CreateClipboardRequest,
    CreateClipboardResponse,
    ListResponse,
)
from copiq_server.application.dedup import find_duplicate
from copiq_server.application.hashing import content_hash
from copiq_server.application.secrets import scan
from copiq_server.auth import require_api_key
from copiq_server.deps import get_db, get_settings_dep
from copiq_server.domain.models import ApiKey, ClipboardItem

router = APIRouter(prefix="/api/clipboard", tags=["clipboard"])

_auth = require_api_key(get_db)


def _to_out(item: ClipboardItem) -> ClipboardItemOut:
    return ClipboardItemOut(
        id=item.id,
        content=item.content,
        content_type=item.content_type,
        source=item.source,
        client_id=item.client_id,
        has_possible_secret=item.has_possible_secret,
        created_at=item.created_at,
    )


@router.post("", response_model=CreateClipboardResponse, status_code=201)
def create_clipboard_item(
    body: CreateClipboardRequest,
    response: Response,
    db: Session = Depends(get_db),
    settings=Depends(get_settings_dep),
    _key: ApiKey = Depends(_auth),
) -> CreateClipboardResponse:
    # architecture.md 14.1 -- size limit, enforced before storage
    if len(body.content.encode("utf-8")) > settings.clipboard.max_content_length:
        raise HTTPException(status_code=413, detail="content exceeds clipboard.max_content_length")

    chash = content_hash(body.content)

    duplicate = find_duplicate(
        db,
        content_hash=chash,
        client_id=body.client_id,
        window_seconds=settings.deduplication.window_seconds,
        scope_to_client=settings.deduplication.scope_to_client,
    )
    if duplicate is not None:
        response.status_code = 200
        return CreateClipboardResponse(id=duplicate.id, created_at=duplicate.created_at, deduplicated=True)

    scan_result = scan(body.content) if settings.secret_detection.enabled else None

    item = ClipboardItem(
        content=body.content,
        content_hash=chash,
        content_type=body.content_type,
        source=body.source,
        client_id=body.client_id,
        has_possible_secret=bool(scan_result and scan_result.flagged),
    )
    db.add(item)
    db.commit()
    db.refresh(item)

    return CreateClipboardResponse(id=item.id, created_at=item.created_at, deduplicated=False)


@router.get("", response_model=ListResponse)
def list_clipboard_items(
    limit: int = Query(default=50, ge=1, le=200),
    before: int | None = None,
    search: str | None = None,
    client_id: str | None = Query(default=None, alias="clientId"),
    db: Session = Depends(get_db),
    _key: ApiKey = Depends(_auth),
) -> ListResponse:
    stmt = select(ClipboardItem).order_by(ClipboardItem.id.desc())
    if before is not None:
        stmt = stmt.where(ClipboardItem.id < before)
    if search:
        stmt = stmt.where(ClipboardItem.content.like(f"%{search}%"))
    if client_id:
        stmt = stmt.where(ClipboardItem.client_id == client_id)

    rows = list(db.execute(stmt.limit(limit + 1)).scalars())
    has_more = len(rows) > limit
    rows = rows[:limit]

    return ListResponse(
        items=[_to_out(r) for r in rows],
        next_cursor=rows[-1].id if rows and has_more else None,
        has_more=has_more,
    )


@router.get("/{item_id}", response_model=ClipboardItemOut)
def get_clipboard_item(
    item_id: int, db: Session = Depends(get_db), _key: ApiKey = Depends(_auth)
) -> ClipboardItemOut:
    item = db.get(ClipboardItem, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="clipboard item not found")
    return _to_out(item)


@router.delete("/{item_id}", status_code=204)
def delete_clipboard_item(
    item_id: int, db: Session = Depends(get_db), _key: ApiKey = Depends(_auth)
) -> Response:
    item = db.get(ClipboardItem, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="clipboard item not found")
    db.delete(item)
    db.commit()
    return Response(status_code=204)
