"""Text-to-speech endpoint. synthesize() is replaced so tests never call
Microsoft's online service."""
from __future__ import annotations

import pytest

from copiq_server.api import audio


@pytest.fixture
def fake_tts(monkeypatch):
    calls: list[str] = []

    async def _fake(text: str) -> bytes:
        calls.append(text)
        return b"ID3fake-mp3"

    monkeypatch.setattr(audio, "synthesize", _fake)
    return calls


def _upload(client, content):
    r = client.post("/api/clipboard", json={"content": content, "source": "x", "clientId": "c1"})
    return r.json()["id"]


def test_audio_returns_mp3_of_item_content(client, fake_tts):
    item_id = _upload(client, "Read this sentence aloud.")
    r = client.get(f"/api/clipboard/{item_id}/audio")
    assert r.status_code == 200
    assert r.headers["content-type"] == "audio/mpeg"
    assert r.content == b"ID3fake-mp3"
    assert fake_tts == ["Read this sentence aloud."]


def test_audio_unknown_item_is_404(client, fake_tts):
    assert client.get("/api/clipboard/999999/audio").status_code == 404


def test_audio_blocks_flagged_secret_unless_acknowledged(client, fake_tts):
    item_id = _upload(client, "AKIAIOSFODNN7EXAMPLE")
    assert client.get(f"/api/clipboard/{item_id}/audio").status_code == 409
    assert fake_tts == []
    r = client.get(f"/api/clipboard/{item_id}/audio", params={"acknowledgeSecret": "true"})
    assert r.status_code == 200


def test_audio_tts_failure_is_502(client, monkeypatch):
    async def _boom(text: str) -> bytes:
        raise RuntimeError("network down")

    monkeypatch.setattr(audio, "synthesize", _boom)
    item_id = _upload(client, "hello")
    assert client.get(f"/api/clipboard/{item_id}/audio").status_code == 502
