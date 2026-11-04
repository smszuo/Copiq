"""Settings defaults and env-var overrides -- architecture.md section 31.0
("Binding the server beyond localhost")."""
from __future__ import annotations

from copiq_server.config import Settings


def test_server_host_and_port_default_to_localhost_only():
    settings = Settings()
    assert settings.server_host == "127.0.0.1"
    assert settings.server_port == 5080


def test_server_host_and_port_overridable_via_env(monkeypatch):
    monkeypatch.setenv("COPIQ_SERVER_HOST", "0.0.0.0")
    monkeypatch.setenv("COPIQ_SERVER_PORT", "9000")

    settings = Settings()

    assert settings.server_host == "0.0.0.0"
    assert settings.server_port == 9000
