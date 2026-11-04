"""FastAPI dependency wiring.

Lazily constructed and cached, rather than built at import time -- tests
override get_db / get_settings_dep / get_ai_provider via
app.dependency_overrides, and eagerly opening a database file on import
would fight that (and litter the cwd with a stray copiq.db on `import`
alone).
"""
from __future__ import annotations

from collections.abc import Generator
from functools import lru_cache

from sqlalchemy.orm import Session

from copiq_server.config import Settings, get_settings
from copiq_server.db import create_all, make_engine, make_session_factory


@lru_cache
def get_settings_dep() -> Settings:
    return get_settings()


@lru_cache
def _engine():
    settings = get_settings_dep()
    engine = make_engine(settings.database_url)
    create_all(engine)
    return engine


@lru_cache
def _session_factory():
    return make_session_factory(_engine())


def get_db() -> Generator[Session, None, None]:
    db = _session_factory()()
    try:
        yield db
    finally:
        db.close()


@lru_cache
def get_ai_provider():
    from copiq_server.providers.claude_cli import ClaudeCliProvider

    settings = get_settings_dep()
    return ClaudeCliProvider(model=settings.ai.model, timeout_seconds=settings.ai.timeout_seconds)
