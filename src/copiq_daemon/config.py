"""Daemon config -- architecture.md section 27.

Shares the config *file* (~/.config/copiq/config.json) and shape with the
CLI, since both are the same "client" concept, but does not import the CLI
package -- copiq_daemon and copiq_cli must stay independently
installable (a headless box might run only the CLI; a desktop might run
only the daemon).
"""
from __future__ import annotations

import json
import os
import stat
from pathlib import Path

_env_override = os.environ.get("COPIQ_CONFIG")
CONFIG_PATH = Path(_env_override) if _env_override else (Path.home() / ".config" / "copiq" / "config.json")


class ConfigError(RuntimeError):
    pass


def load_config() -> dict:
    if not CONFIG_PATH.exists():
        raise ConfigError(
            f"no config at {CONFIG_PATH}. Create it with:\n"
            '  {"server": "http://localhost:5080", "apiKey": "cw_..."}'
        )

    mode = CONFIG_PATH.stat().st_mode
    if mode & (stat.S_IRWXG | stat.S_IRWXO):
        raise ConfigError(
            f"{CONFIG_PATH} is readable by other users on this machine "
            f"(it holds your API key). Fix with: chmod 600 {CONFIG_PATH}"
        )

    with CONFIG_PATH.open() as f:
        data = json.load(f)

    if "server" not in data or "apiKey" not in data:
        raise ConfigError(f"{CONFIG_PATH} must have 'server' and 'apiKey'")

    return data
