"""Retention -- architecture.md section 30.

AI results follow their source item's retention automatically via the
ON DELETE CASCADE foreign key (section 12) -- deleting the clipboard item
is enough; there is no separate cleanup for ai_action_results.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import delete
from sqlalchemy.orm import Session

from copiq_server.domain.models import ClipboardItem


def purge_expired(db: Session, *, days: int) -> int:
    """Delete clipboard items older than `days`. Returns the number removed.
    days <= 0 means "forever" -- never purge."""
    if days <= 0:
        return 0

    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
    result = db.execute(delete(ClipboardItem).where(ClipboardItem.created_at < cutoff))
    db.commit()
    return result.rowcount
