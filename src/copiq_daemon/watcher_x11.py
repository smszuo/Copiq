"""X11 clipboard watcher -- architecture.md section 6.1.

Event-driven via the XFIXES extension, not polled: subscribing to
CLIPBOARD owner-change costs nothing while idle, versus ~172,000 process
spawns/day polling `xclip -o` at 500ms. Verified against this project's own
X11 session with python-xlib (pure Python, no system deps) during design.

If this machine ever moves to Wayland, replace this module with
`wl-paste --watch` behind the same async-iterator interface -- nothing
else in the daemon should need to change (section 6.1).
"""
from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator

from Xlib import X, display
from Xlib.ext import xfixes


class ClipboardWatcher:
    """Yields the clipboard's text content each time it changes."""

    def __init__(self) -> None:
        self._display = display.Display()
        if not self._display.has_extension("XFIXES"):
            raise RuntimeError("XFIXES extension not available on this X server")
        self._display.xfixes_query_version()

        self._window = self._display.screen().root.create_window(0, 0, 1, 1, 0, X.CopyFromParent)
        self._clipboard_atom = self._display.get_atom("CLIPBOARD")
        self._utf8_atom = self._display.get_atom("UTF8_STRING")
        self._targets_atom = self._display.get_atom("TARGETS")

        self._display.xfixes_select_selection_input(
            self._window, self._clipboard_atom, xfixes.XFixesSetSelectionOwnerNotifyMask
        )
        self._display.flush()

    async def changes(self) -> AsyncIterator[str]:
        loop = asyncio.get_event_loop()
        while True:
            # next_event() blocks the underlying socket read; run it off the
            # event loop thread so the daemon can still be cancelled cleanly.
            await loop.run_in_executor(None, self._display.next_event)
            text = self._read_selection()
            if text is not None:
                yield text

    def _read_selection(self) -> str | None:
        owner = self._display.get_selection_owner(self._clipboard_atom)
        if owner == X.NONE:
            return None

        prop_name = self._display.get_atom("COPIQ_SEL")
        self._window.convert_selection(
            self._clipboard_atom, self._utf8_atom, prop_name, X.CurrentTime
        )
        self._display.sync()

        # SelectionNotify should follow shortly; drain events for it.
        for _ in range(10):
            ev = self._display.next_event()
            if ev.type == X.SelectionNotify:
                break
        else:
            return None

        prop = self._window.get_full_property(prop_name, X.AnyPropertyType)
        if prop is None:
            return None
        try:
            return prop.value.decode("utf-8")
        except UnicodeDecodeError:
            return None

    def close(self) -> None:
        self._display.close()
