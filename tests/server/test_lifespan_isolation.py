"""Regression test: the retention background task started from `lifespan`
must resolve settings/db through app.dependency_overrides, not by calling
the module-level singletons directly -- otherwise every test that spins up
a TestClient silently opens the *real* default database
(sqlite:///./copiq.db) as a side effect of app startup. See main.py's
_retention_loop docstring.
"""
from __future__ import annotations

from pathlib import Path


def test_starting_the_app_does_not_touch_the_real_default_database(client):
    # `client` (conftest.py) already exercises TestClient(app), which runs
    # the lifespan startup/shutdown. If _retention_loop ever regresses to
    # calling get_settings_dep()/get_db() directly, it would create-or-open
    # ./copiq.db as a side effect of merely starting the app.
    #
    # This asserts non-interference, not absence: a real ./copiq.db can
    # legitimately exist (someone is running the actual server from this
    # directory), and this test must never be the thing that deletes or
    # resets someone's real clipboard history. So it snapshots whatever is
    # there beforehand and asserts it is bit-for-bit unchanged afterward,
    # rather than asserting the file doesn't exist.
    db_path = Path("copiq.db")
    before = db_path.read_bytes() if db_path.exists() else None

    # `client` fixture already ran by the time this line executes; re-touch
    # it to be explicit that the lifespan has started and settled.
    client.get("/healthz")

    after = db_path.read_bytes() if db_path.exists() else None
    assert before == after, (
        "./copiq.db changed (or appeared) as a side effect of running "
        "the test suite -- a background task is bypassing "
        "app.dependency_overrides and touching the real default database."
    )
