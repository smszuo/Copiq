"""Upload to the Copiq server -- architecture.md section 5.1.

The daemon deduplicates only against the *value it just uploaded* -- a pure
optimization on exact last-value match, never a substitute for the server's
authoritative dedup (section 13.1). Suppressing more than that here would
mean an entry silently never reaching the server after e.g. a daemon
restart clears this in-memory state -- data loss that is very hard to
diagnose from outside the client.
"""
from __future__ import annotations

import json
import logging
import socket

import httpx

logger = logging.getLogger("copiq_daemon")


class Uploader:
    def __init__(self, server: str, api_key: str, client_id: str | None = None) -> None:
        self._client = httpx.Client(
            base_url=server,
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=10.0,
        )
        self._client_id = client_id or socket.gethostname()
        self._last_uploaded: str | None = None

    def upload(self, content: str) -> None:
        if content == self._last_uploaded:
            return  # exact repeat of our own last upload -- section 6.1's "not deduplicated further than this"

        try:
            resp = self._client.post(
                "/api/clipboard",
                json={"content": content, "source": "copiq-daemon", "clientId": self._client_id},
            )
            resp.raise_for_status()
            self._last_uploaded = content
            body = resp.json()
            # Never log clipboard content by default (architecture.md section 28/34).
            logger.info(
                "uploaded id=%s deduplicated=%s len=%d",
                body.get("id"), body.get("deduplicated"), len(content),
            )
        except httpx.HTTPStatusError as e:
            logger.warning("upload rejected: %s", e.response.status_code)
        except httpx.HTTPError as e:
            logger.warning("upload failed: %s", e)

    def close(self) -> None:
        self._client.close()
