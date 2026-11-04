# Copiq

Clipboard history + developer-oriented AI actions. See `docs/architecture.md`
for the full design; this is the short version for getting it running.

The primary workflow: copy English output from Claude Code in your terminal,
then translate/explain/simplify/diagram it without leaving the keyboard.

## Prerequisites

- Python 3.12 (pinned via `.python-version`; `uv` provisions it automatically)
- [uv](https://docs.astral.sh/uv/)
- The `claude` CLI, installed and logged in (`claude --version` should work).
  `ClaudeCliProvider` (architecture.md section 17.1) reuses this login --
  no separate API key is needed for AI actions.
- Linux: X11 (for the clipboard daemon only -- section 6.1). macOS: no
  extra prerequisite -- the daemon uses AppKit via `pyobjc`, installed
  automatically as a platform-conditional dependency. The server and CLI
  have no display requirement on either OS.
- Node.js 20+ and npm, only for building/running the Web UI
  (`web/copiq-web`). The server, CLI, and daemon have no Node dependency.

## Setup

```bash
uv sync --extra dev
```

(The project's own `uv.toml` points at the public PyPI index, overriding a
broken mirror+proxy some machines have configured globally in
`~/.config/uv/uv.toml` -- if `uv` still can't reach anything, that global
config is the thing to check.)

Create the database and an API key:

```bash
./scripts/create_api_key.py --name my-laptop
# or: uv run python scripts/create_api_key.py --name my-laptop
```

This prints a key once (`cw_...`) -- it is stored only as a hash (section
27.1), so save it now. Put it in `~/.config/copiq/config.json`:

```bash
mkdir -p ~/.config/copiq
cat > ~/.config/copiq/config.json <<JSON
{"server": "http://127.0.0.1:5080", "apiKey": "cw_..."}
JSON
chmod 600 ~/.config/copiq/config.json
```

(Optional) copy `copiq.toml.example` to `copiq.toml` to change any
default -- model, target language, retention window, etc. To reach the
server from another machine, set `server_host = "0.0.0.0"` there (or
`COPIQ_SERVER_HOST=0.0.0.0`/`COPIQ_SERVER_PORT=...` env vars) -- only when
running via `copiq-server`, not the raw `uvicorn ...` command below, which
takes its own `--host`/`--port` instead. See architecture.md section 31.0
for the security tradeoffs of binding beyond localhost.

## Run

```bash
uv run uvicorn copiq_server.main:app --port 5080 --reload   # API, http://127.0.0.1:5080
uv run python -m copiq_daemon                                # clipboard watcher (X11 on Linux, AppKit on macOS)
uv run python -m copiq_cli list                              # or just `copiq list` after `uv tool install`
```

Web UI (architecture.md section 8.4) is a separate React project. For
development, in a fourth terminal:

```bash
cd web/copiq-web
npm install
npm run dev             # http://localhost:5173, hot reload, CORS to the API
```

The first time it loads, it'll ask for the server URL and an API key (the one
from `create_api_key.py` above) -- these are stored in the browser's
localStorage, not on disk.

For a single process instead of two, build once and let the API server serve
the result:

```bash
cd web/copiq-web && npm install && npm run build && cd ../..
uv run uvicorn copiq_server.main:app --port 5080
# now http://127.0.0.1:5080 serves both the API and the Web UI
```

For always-on use, see `deploy/*.service` (systemd user units, Linux) or
`deploy/com.copiq.daemon.plist` (LaunchAgent, macOS) -- section 31.0.

## CLI

```bash
copiq list
copiq search "race condition"
copiq get [128]
copiq translate [128] [--lang ja-JP]
copiq explain [128]
copiq simplify [128]
copiq diagram [128] [--type flowchart|sequence|class|er]
copiq delete [128]
```

The id is optional on every item-scoped command -- omit it and the command
acts on the most recently captured clipboard item, matching the actual
workflow: copy something, then act on it, without a `list` round trip just to
read off an id.

Install it as a standalone command (bypasses the pyenv shim -- section 8.2).
This also installs `copiq-server`/`copiq-daemon` on your PATH -- there's no
way to cherry-pick just one script from a project's `uv tool install`:

```bash
uv tool install --editable .
```

## Test

```bash
uv run pytest
```

62 tests: unit tests for dedup/hashing, the secret scanner (both directions --
true positives and the false-positive exclusions), cache-key stability,
parameter normalization (including diagram type validation and the Mermaid
fence-extraction postprocessing, section 21.1), retention/cascade, and the
wire-contract sync check (section 9.1); integration tests against a real
(temporary-file) SQLite database and FastAPI's TestClient, using
`FakeAiProvider` so no `claude` subprocess runs during `pytest`.

There is no automated test suite for the Web UI (`npx tsc -b` typechecks it,
but nothing exercises rendered behavior). Section 8.4.2 explains why this
matters more than it might sound: the previous frontend's actual bug was
invisible to every check *except* a real browser with an instrumented
`MutationObserver` -- if the Web UI grows past what a glance in the browser
can cover, that's the first testing gap worth closing, not another Python
test.

## What's implemented

Phases 1-4 from architecture.md section 40, plus a first cut of Phase 5:

- Server: clipboard CRUD + cursor pagination, dedup (13.1), secret scanner
  (29), API-key auth (27.1), retention purge (30, cascades via the FK -- no
  separate job for AI results).
- AI: `translate` / `explain` / `simplify` / `diagram` via `ClaudeCliProvider`
  (17.1), cache-key upsert (22), versioned prompts (18), per-action model
  overrides (17, `[ai.model_overrides]`), and per-action prompt overrides
  (18.2, `[prompts]`) -- every prompt is replaceable via config, no code
  change needed.
- CLI: `copiq`, stdlib-only for startup speed (8.2).
- Daemon: X11/XFIXES clipboard watcher (6.1), verified working against this
  project's own display during design; a macOS backend (AppKit/NSPasteboard
  polling, same section) is implemented but not yet verified on real
  hardware.
- Web UI: React + TypeScript + Tailwind CSS (8.4) -- history, search,
  per-item actions, delete, full-screen + light/dark/system-themed Mermaid
  diagram rendering (21.1) via a dynamically-imported `mermaid` (kept out
  of the eager bundle -- see 21.1 for the before/after numbers). Talks to
  the same REST API as the CLI, with its own real API key (see
  `web/copiq-web/src/lib/settings.ts`) rather than
  any special-cased browser trust.

Not implemented: SSE (26), PostgreSQL (8.1), Alembic migrations (schema is
created via `Base.metadata.create_all` for now -- fine while the schema is
still moving; add Alembic once it stabilizes), browser/VS Code extensions
and vocabulary tracking (38), multi-user anything.
