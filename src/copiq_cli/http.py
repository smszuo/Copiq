"""Minimal HTTP client -- stdlib http.client only (architecture.md 8.2).

No requests, no httpx: this CLI makes one request per invocation and exits,
so a connection-pooling client's import cost buys nothing here.
"""
from __future__ import annotations

import http.client
import json
from urllib.parse import urlencode, urlsplit


class ApiError(RuntimeError):
    def __init__(self, status: int, body: dict | str) -> None:
        self.status = status
        self.body = body
        super().__init__(f"HTTP {status}: {body}")


def request(
    server: str,
    api_key: str,
    method: str,
    path: str,
    *,
    params: dict | None = None,
    json_body: dict | None = None,
    timeout: float = 30,
) -> dict:
    parts = urlsplit(server)
    conn_cls = http.client.HTTPSConnection if parts.scheme == "https" else http.client.HTTPConnection
    conn = conn_cls(parts.hostname, parts.port or (443 if parts.scheme == "https" else 80), timeout=timeout)

    full_path = path
    if params:
        clean = {k: v for k, v in params.items() if v is not None}
        if clean:
            full_path += "?" + urlencode(clean)

    headers = {"Authorization": f"Bearer {api_key}", "Accept": "application/json"}
    body = None
    if json_body is not None:
        body = json.dumps(json_body).encode("utf-8")
        headers["Content-Type"] = "application/json"

    try:
        conn.request(method, full_path, body=body, headers=headers)
        resp = conn.getresponse()
        raw = resp.read()
    finally:
        conn.close()

    if resp.status == 204:
        return {}

    try:
        data = json.loads(raw) if raw else {}
    except json.JSONDecodeError:
        data = raw.decode("utf-8", "replace")

    if resp.status >= 400:
        raise ApiError(resp.status, data)

    return data
