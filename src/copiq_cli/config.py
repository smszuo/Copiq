"""Client config -- architecture.md section 27.

JSON, not TOML: the CLI already imports `json` to parse API responses, so
reading its own config costs nothing extra; adding tomllib would spend
another import against the startup budget (section 8.2) for no benefit.
"""
from __future__ import annotations

import json
import os
import stat
import sys
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
        # Refuse rather than warn (section 27.1): a silent warning about a
        # readable credential file is a warning nobody reads.
        raise ConfigError(
            f"{CONFIG_PATH} is readable by other users on this machine "
            f"(it holds your API key). Fix with: chmod 600 {CONFIG_PATH}"
        )

    with CONFIG_PATH.open() as f:
        data = json.load(f)

    if "server" not in data or "apiKey" not in data:
        raise ConfigError(f"{CONFIG_PATH} must have 'server' and 'apiKey'")

    return data
