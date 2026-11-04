"""Deduplication -- architecture.md section 13 + 13.1.

The server is authoritative. Same hash + same client + within the configured
window = duplicate. POST /api/clipboard is idempotent within that window.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from copiq_server.domain.models import ClipboardItem


def _parse_iso(ts: str) -> datetime:
    return datetime.strptime(ts, "%Y-%m-%dT%H:%M:%S.%f%z" if "." in ts else "%Y-%m-%dT%H:%M:%S%z")


def find_duplicate(
    db: Session,
    *,
    content_hash: str,
    client_id: str,
    window_seconds: int,
    scope_to_client: bool,
) -> ClipboardItem | None:
    """Return the existing item this upload duplicates, or None."""
    now = datetime.now(timezone.utc)
    cutoff = (now - timedelta(seconds=window_seconds)).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"

    stmt = (
        select(ClipboardItem)
        .where(ClipboardItem.content_hash == content_hash)
        .where(ClipboardItem.created_at >= cutoff)
    )
    if scope_to_client:
        stmt = stmt.where(ClipboardItem.client_id == client_id)
    stmt = stmt.order_by(ClipboardItem.created_at.desc()).limit(1)

    return db.execute(stmt).scalar_one_or_none()
