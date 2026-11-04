#!/usr/bin/env -S uv run python
"""Provision a client API key -- architecture.md section 27.1.

    uv run python scripts/create_api_key.py --name my-laptop

or, since it's executable and `uv run` finds the project from any
subdirectory:

    ./scripts/create_api_key.py --name my-laptop

The old shebang (`#!/usr/bin/env python`) ran whatever `python` happened
to be first on $PATH -- usually not this project's venv, hence
`ModuleNotFoundError: No module named 'copiq_server'` when run directly.
`uv run` resolves this project's own environment regardless of what's on
$PATH or which directory it's invoked from.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path

from copiq_server.auth import generate_key, hash_key
from copiq_server.config import get_settings
from copiq_server.db import create_all, make_engine, make_session_factory
from copiq_server.domain.models import ApiKey

# copiq_server.config.Settings resolves both the sqlite path
# ("sqlite:///./copiq.db") and the optional copiq.toml file relative to the
# current working directory -- by design, since that's what lets the
# systemd units (deploy/*.service) point one WorkingDirectory at a data
# directory. But this script is a project utility, not a deployed server:
# run from anywhere other than the project root (e.g. `cd scripts &&
# ./create_api_key.py`), it would silently create-and-use a *different*,
# empty database in whatever directory happened to be current, rather
# than erroring -- provisioning a key that's real but useless, against a
# database the actual running server never reads. Anchor to the project
# root unconditionally so this script always means "the project's
# database", regardless of the caller's cwd.
os.chdir(Path(__file__).resolve().parent.parent)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--name", required=True)
    args = parser.parse_args()

    settings = get_settings()
    engine = make_engine(settings.database_url)
    create_all(engine)
    db = make_session_factory(engine)()

    raw_key = generate_key()
    db.add(ApiKey(name=args.name, key_hash=hash_key(raw_key)))
    db.commit()

    print(raw_key)


if __name__ == "__main__":
    main()
