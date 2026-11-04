"""macOS-only: requires AppKit/pyobjc, so this whole module is skipped
everywhere except a `macos-latest` CI job (see docs/architecture.md 6.1).
"""
from __future__ import annotations

import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

if sys.platform != "darwin":
    pytest.skip("macOS-only: requires AppKit/pyobjc", allow_module_level=True)

from AppKit import NSPasteboardTypeString  # noqa: E402
from copiq_daemon.watcher_macos import ClipboardWatcher  # noqa: E402


def _watcher_with(pasteboard: MagicMock) -> ClipboardWatcher:
    with patch("copiq_daemon.watcher_macos.NSPasteboard") as ns_pasteboard:
        ns_pasteboard.generalPasteboard.return_value = pasteboard
        return ClipboardWatcher()


async def test_yields_text_only_when_change_count_bumps():
    pasteboard = MagicMock()
    pasteboard.changeCount.side_effect = [5, 5, 6]
    pasteboard.stringForType_.return_value = "hello"

    watcher = _watcher_with(pasteboard)
    with patch("copiq_daemon.watcher_macos.asyncio.sleep", new=AsyncMock()):
        result = await anext(watcher.changes())

    assert result == "hello"
    assert pasteboard.changeCount.call_count == 3  # baseline + 2 polls
    pasteboard.stringForType_.assert_called_once_with(NSPasteboardTypeString)


async def test_skips_change_with_no_string_content():
    pasteboard = MagicMock()
    # baseline 5; poll 1 bumps to 6 but pasteboard has no string (e.g. an
    # image copy); poll 2 sees no further change; poll 3 bumps to 7 with text.
    pasteboard.changeCount.side_effect = [5, 6, 6, 7]
    pasteboard.stringForType_.side_effect = [None, "second"]

    watcher = _watcher_with(pasteboard)
    with patch("copiq_daemon.watcher_macos.asyncio.sleep", new=AsyncMock()):
        result = await anext(watcher.changes())

    assert result == "second"
    assert pasteboard.stringForType_.call_count == 2


async def test_close_is_a_no_op():
    watcher = _watcher_with(MagicMock(changeCount=MagicMock(return_value=0)))
    watcher.close()  # must not raise
