"""architecture.md section 30 -- retention purges old items; AI results
follow via ON DELETE CASCADE (section 12), not a second purge query."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from copiq_server.application.retention import purge_expired
from copiq_server.domain.models import AiActionResult, ClipboardItem


def _iso(dt) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def test_purge_removes_items_older_than_window(session_factory):
    db = session_factory()
    old = ClipboardItem(
        content="old", content_hash="h1", content_type="text/plain",
        source="x", client_id="c1",
        created_at=_iso(datetime.now(timezone.utc) - timedelta(days=40)),
    )
    fresh = ClipboardItem(
        content="fresh", content_hash="h2", content_type="text/plain",
        source="x", client_id="c1",
        created_at=_iso(datetime.now(timezone.utc)),
    )
    db.add_all([old, fresh])
    db.commit()

    removed = purge_expired(db, days=30)
    assert removed == 1

    remaining = db.query(ClipboardItem).all()
    assert [i.content for i in remaining] == ["fresh"]


def test_purge_zero_days_means_forever(session_factory):
    db = session_factory()
    db.add(ClipboardItem(
        content="ancient", content_hash="h1", content_type="text/plain",
        source="x", client_id="c1",
        created_at=_iso(datetime.now(timezone.utc) - timedelta(days=9999)),
    ))
    db.commit()

    removed = purge_expired(db, days=0)
    assert removed == 0
    assert db.query(ClipboardItem).count() == 1


def test_purge_cascades_to_ai_results(session_factory):
    db = session_factory()
    item = ClipboardItem(
        content="old", content_hash="h1", content_type="text/plain",
        source="x", client_id="c1",
        created_at=_iso(datetime.now(timezone.utc) - timedelta(days=40)),
    )
    db.add(item)
    db.commit()
    db.add(AiActionResult(
        clipboard_item_id=item.id, cache_key="k1", action="translate",
        provider="fake", model="fake", prompt_version="v1", status="completed",
        result="x",
    ))
    db.commit()

    purge_expired(db, days=30)

    assert db.query(ClipboardItem).count() == 0
    assert db.query(AiActionResult).count() == 0
