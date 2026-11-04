"""Read a clipboard item aloud with edge-tts (Microsoft Edge's online
text-to-speech service). The text leaves this machine, so the same secret
gate and size limit as the AI actions apply."""
from __future__ import annotations

import edge_tts
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session

from copiq_server.auth import require_api_key
from copiq_server.deps import get_db, get_settings_dep
from copiq_server.domain.models import ApiKey, ClipboardItem

router = APIRouter(prefix="/api/clipboard", tags=["audio"])

_auth = require_api_key(get_db)

VOICE = "en-US-AndrewNeural"  # US English, male


async def synthesize(text: str) -> bytes:
    communicate = edge_tts.Communicate(text, VOICE)
    return b"".join([c["data"] async for c in communicate.stream() if c["type"] == "audio"])


@router.get("/{item_id}/audio")
async def get_clipboard_audio(
    item_id: int,
    acknowledge_secret: bool = Query(False, alias="acknowledgeSecret"),
    db: Session = Depends(get_db),
    settings=Depends(get_settings_dep),
    _key: ApiKey = Depends(_auth),
) -> Response:
    item = db.get(ClipboardItem, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="clipboard item not found")
    if item.has_possible_secret and not (acknowledge_secret and settings.secret_detection.allow_override):
        raise HTTPException(status_code=409, detail="content flagged by secret scanner: see clipboard item flag")
    if len(item.content) > settings.ai.max_input_length:
        raise HTTPException(
            status_code=413,
            detail=f"content ({len(item.content)} chars) exceeds ai.max_input_length ({settings.ai.max_input_length})",
        )

    try:
        audio = await synthesize(item.content)
    except Exception as e:  # network errors, NoAudioReceived, ... -- all mean the TTS service failed
        raise HTTPException(status_code=502, detail=f"text-to-speech failed: {e}") from e
    if not audio:
        raise HTTPException(status_code=502, detail="text-to-speech returned no audio")
    return Response(content=audio, media_type="audio/mpeg")
