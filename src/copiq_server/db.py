"""Engine + session management. Enforces PRAGMA foreign_keys=ON per connection
(architecture.md section 12) -- SQLite ignores FKs otherwise, which would make
the ON DELETE CASCADE on ai_action_results silently inert."""
from __future__ import annotations

from collections.abc import Generator
from sqlalchemy import Engine, event
from sqlalchemy.orm import Session, sessionmaker

from copiq_server.domain.models import Base


def make_engine(database_url: str) -> Engine:
    from sqlalchemy import create_engine

    connect_args = {"check_same_thread": False} if database_url.startswith("sqlite") else {}
    engine = create_engine(database_url, connect_args=connect_args)

    @event.listens_for(engine, "connect")
    def _fk_on(dbapi_conn, _):
        if database_url.startswith("sqlite"):
            cursor = dbapi_conn.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    return engine


def create_all(engine: Engine) -> None:
    Base.metadata.create_all(engine)


def make_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
