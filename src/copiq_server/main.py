"""ASGI app assembly. `uvicorn copiq_server.main:app` or `copiq-server`.

Web UI -- architecture.md section 8.4, 25 -- is a React + TypeScript SPA
(web/copiq-web) built with Vite and styled with Tailwind CSS, built to
static files and served here. Unlike the earlier Jinja2+HTMX version, the
API is untouched by the choice of frontend: the React app is just another
client presenting a real Bearer token, exactly like the CLI and daemon
(see auth.py) -- there's no special-cased auth path for it.
"""
from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from copiq_server.api import actions, audio, clipboard
from copiq_server.application.retention import purge_expired
from copiq_server.config import get_settings
from copiq_server.deps import _session_factory, get_db, get_settings_dep

logger = logging.getLogger("copiq_server")

_RETENTION_CHECK_INTERVAL_SECONDS = 3600  # once an hour is plenty for a daily policy

# The Vite dev server's default origin. Only relevant in development -- the
# production build is served from this same origin (below), so no CORS is
# involved once you're running against `dist/`.
_DEV_ORIGINS = ["http://localhost:5173", "http://127.0.0.1:5173"]


async def _retention_loop(app: FastAPI) -> None:
    """architecture.md section 30 -- no message broker in the MVP (section
    36), so this is a plain asyncio background task, not a scheduler.

    Resolves settings/db through `app.dependency_overrides` rather than
    calling the module-level singletons directly -- a background task
    started from `lifespan` sits outside FastAPI's per-request DI, so
    calling `get_settings_dep()` / `get_db()` directly would silently ignore
    whatever a test substituted via `app.dependency_overrides`, and open the
    *real* default database as a side effect of just starting the app.
    """
    while True:
        try:
            settings_dep = app.dependency_overrides.get(get_settings_dep, get_settings_dep)
            settings = settings_dep()

            db_dep = app.dependency_overrides.get(get_db, get_db)
            db_gen = db_dep()
            db = next(db_gen)
            try:
                removed = purge_expired(db, days=settings.retention.days)
                if removed:
                    logger.info("retention: purged %d expired clipboard item(s)", removed)
            finally:
                next(db_gen, None)  # drive the generator's `finally: db.close()`
        except Exception:
            logger.exception("retention purge failed")
        await asyncio.sleep(_RETENTION_CHECK_INTERVAL_SECONDS)


@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(_retention_loop(app))
    try:
        yield
    finally:
        task.cancel()


app = FastAPI(title="Copiq", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_DEV_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(clipboard.router)
app.include_router(actions.router)
app.include_router(audio.router)


@app.get("/healthz")
def healthz() -> dict[str, bool]:
    return {"ok": True}


# The built React app (`npm run build` in web/copiq-web), mounted last so
# the API routes above take precedence. `html=True` serves index.html for
# unmatched paths, which is what a client-side SPA needs.
_dist_dir = Path(__file__).resolve().parent.parent.parent / "web" / "copiq-web" / "dist"
if _dist_dir.is_dir():
    app.mount("/", StaticFiles(directory=str(_dist_dir), html=True), name="web")
else:
    logger.warning(
        "%s not found -- run `npm run build` in web/copiq-web to serve the "
        "Web UI from this server. The API still works without it (use the "
        "Vite dev server at :5173 in the meantime).",
        _dist_dir,
    )


def run() -> None:
    import uvicorn

    settings = get_settings()
    uvicorn.run(
        "copiq_server.main:app", host=settings.server_host, port=settings.server_port, reload=False
    )


if __name__ == "__main__":
    run()
