"""architecture.md section 14 + 33 (integration tests)."""
from __future__ import annotations


def test_create_and_get(client):
    r = client.post("/api/clipboard", json={
        "content": "This looks like a race condition.",
        "source": "clipboard-client",
        "clientId": "desktop-01",
    })
    assert r.status_code == 201
    body = r.json()
    assert body["deduplicated"] is False
    item_id = body["id"]

    r = client.get(f"/api/clipboard/{item_id}")
    assert r.status_code == 200
    assert r.json()["content"] == "This looks like a race condition."
    assert r.json()["hasPossibleSecret"] is False


def test_get_missing_returns_404(client):
    r = client.get("/api/clipboard/999999")
    assert r.status_code == 404


def test_no_api_key_rejected(client):
    client.headers.pop("Authorization")
    r = client.get("/api/clipboard")
    assert r.status_code == 401


def test_wrong_api_key_rejected(client):
    client.headers["Authorization"] = "Bearer cw_wrong"
    r = client.get("/api/clipboard")
    assert r.status_code == 401


def test_dedup_returns_200_and_existing_id(client):
    payload = {"content": "duplicate me", "source": "x", "clientId": "c1"}
    r1 = client.post("/api/clipboard", json=payload)
    assert r1.status_code == 201
    r2 = client.post("/api/clipboard", json=payload)
    assert r2.status_code == 200
    assert r2.json()["deduplicated"] is True
    assert r2.json()["id"] == r1.json()["id"]


def test_dedup_scoped_to_client(client):
    payload_a = {"content": "same text", "source": "x", "clientId": "a"}
    payload_b = {"content": "same text", "source": "x", "clientId": "b"}
    r1 = client.post("/api/clipboard", json=payload_a)
    r2 = client.post("/api/clipboard", json=payload_b)
    assert r1.status_code == 201
    assert r2.status_code == 201  # different client -> not a duplicate
    assert r1.json()["id"] != r2.json()["id"]


def test_content_too_large_rejected(client, settings):
    big = "x" * (settings.clipboard.max_content_length + 1)
    r = client.post("/api/clipboard", json={"content": big, "source": "x", "clientId": "c1"})
    assert r.status_code == 413


def test_list_cursor_pagination(client):
    for i in range(5):
        client.post("/api/clipboard", json={"content": f"item {i}", "source": "x", "clientId": "c1"})

    r = client.get("/api/clipboard", params={"limit": 2})
    assert r.status_code == 200
    body = r.json()
    assert len(body["items"]) == 2
    assert body["hasMore"] is True
    assert body["items"][0]["content"] == "item 4"  # newest first

    next_cursor = body["nextCursor"]
    r2 = client.get("/api/clipboard", params={"limit": 2, "before": next_cursor})
    body2 = r2.json()
    assert all(item["id"] < next_cursor for item in body2["items"])


def test_delete_clipboard_item(client):
    r = client.post("/api/clipboard", json={"content": "delete me", "source": "x", "clientId": "c1"})
    item_id = r.json()["id"]

    r = client.delete(f"/api/clipboard/{item_id}")
    assert r.status_code == 204

    r = client.get(f"/api/clipboard/{item_id}")
    assert r.status_code == 404

    r = client.delete(f"/api/clipboard/{item_id}")
    assert r.status_code == 404


def test_secret_flagged_on_upload_but_still_stored(client):
    r = client.post("/api/clipboard", json={
        "content": "aws key AKIAABCDEFGHIJKLMNOP in this snippet",
        "source": "x", "clientId": "c1",
    })
    assert r.status_code == 201
    item_id = r.json()["id"]
    r = client.get(f"/api/clipboard/{item_id}")
    assert r.json()["hasPossibleSecret"] is True
