"""macOS clipboard watcher -- architecture.md section 6.1.

Polls NSPasteboard.changeCount() rather than pushing events like the X11
path's XFIXES subscription: AppKit has no clipboard-change notification API,
polling is the only option (same approach Maccy/Clipy/Alfred use). This is
not the polling trade-off the X11 path avoids -- docs section 6.1's ~172,000
`xclip` *process spawns*/day -- changeCount() is a single in-process
property read, not a subprocess, so polling it a few times a second costs
nothing worth avoiding.
"""
from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator

from AppKit import NSPasteboard, NSPasteboardTypeString

_POLL_INTERVAL_SECONDS = 0.3


class ClipboardWatcher:
    """Yields the clipboard's text content each time it changes."""

    def __init__(self) -> None:
        self._pasteboard = NSPasteboard.generalPasteboard()
        self._last_change_count = self._pasteboard.changeCount()

    async def changes(self) -> AsyncIterator[str]:
        while True:
            await asyncio.sleep(_POLL_INTERVAL_SECONDS)
            count = self._pasteboard.changeCount()
            if count == self._last_change_count:
                continue
            self._last_change_count = count

            text = self._pasteboard.stringForType_(NSPasteboardTypeString)
            if text is not None:
                yield str(text)

    def close(self) -> None:
        pass
