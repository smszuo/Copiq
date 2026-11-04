"""copiq-daemon -- architecture.md section 6.1.

Monitors the clipboard (X11/XFIXES on Linux, NSPasteboard on macOS) and
uploads changes to the Copiq server. Deliberately thin: no dedup beyond
exact-repeat suppression, no secret scanning -- both belong on the server
(sections 13.1, 29).
"""
from __future__ import annotations

import asyncio
import logging
import sys

from copiq_daemon.config import ConfigError, load_config
from copiq_daemon.uploader import Uploader

logger = logging.getLogger("copiq_daemon")


def _make_watcher():
    # Backend picked by platform, not by feature-detecting the display server --
    # see the per-backend module docstrings for why each one works the way it does.
    if sys.platform == "darwin":
        from copiq_daemon.watcher_macos import ClipboardWatcher
    elif sys.platform.startswith("linux"):
        from copiq_daemon.watcher_x11 import ClipboardWatcher
    else:
        raise RuntimeError(f"copiq-daemon has no clipboard watcher for platform {sys.platform!r}")
    return ClipboardWatcher()


async def _run() -> int:
    try:
        cfg = load_config()
    except ConfigError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1

    watcher = _make_watcher()
    uploader = Uploader(cfg["server"], cfg["apiKey"])
    logger.info("copiq-daemon started, watching clipboard on %s", sys.platform)

    try:
        async for content in watcher.changes():
            if content.strip():
                uploader.upload(content)
    finally:
        uploader.close()
        watcher.close()

    return 0


def run() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    try:
        sys.exit(asyncio.run(_run()))
    except KeyboardInterrupt:
        sys.exit(0)


if __name__ == "__main__":
    run()
