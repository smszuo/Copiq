"""Shared fixtures. Uses a temporary SQLite *file*, not :memory:, per
architecture.md section 33 -- the FK cascade and PRAGMA foreign_keys
connection event behave differently across connections, and :memory: hides
exactly the class of bug this setup exists to catch.
"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from copiq_server.auth import generate_key, hash_key
from copiq_server.config import Settings
from copiq_server.db import create_all, make_engine, make_session_factory
from copiq_server.deps import get_ai_provider, get_db, get_settings_dep
from copiq_server.domain.models import ApiKey
from copiq_server.main import app
from copiq_server.providers.fake import FakeAiProvider


@pytest.fixture
def db_path(tmp_path: Path):
    path = tmp_path / "test.db"
    yield path


@pytest.fixture
def settings(db_path: Path) -> Settings:
    return Settings(database_url=f"sqlite:///{db_path}")


@pytest.fixture
def session_factory(settings: Settings):
    engine = make_engine(settings.database_url)
    create_all(engine)
    return make_session_factory(engine)


@pytest.fixture
def api_key(session_factory) -> str:
    raw = generate_key()
    db = session_factory()
    db.add(ApiKey(name="test-client", key_hash=hash_key(raw)))
    db.commit()
    db.close()
    return raw


@pytest.fixture
def fake_provider() -> FakeAiProvider:
    return FakeAiProvider()


@pytest.fixture
def client(settings, session_factory, fake_provider, api_key):
    def _get_db():
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_settings_dep] = lambda: settings
    app.dependency_overrides[get_db] = _get_db
    app.dependency_overrides[get_ai_provider] = lambda: fake_provider

    with TestClient(app) as c:
        c.headers.update({"Authorization": f"Bearer {api_key}"})
        yield c

    app.dependency_overrides.clear()
