# echonet_client.py
import httpx
from .settings import settings

async def post_text_event(*, source_id: str, room: str | None, ts: int, text: str, confidence: float | None):
    payload = {
        "source_id": source_id,
        "room": room,
        "ts": ts,
        "text": text,
        "confidence": confidence,
    }
    headers = {"X-API-Key": settings.echonet_api_key}
    async with httpx.AsyncClient(timeout=3.0) as client:
        await client.post(settings.echonet_url.rstrip("/") + "/text", json=payload, headers=headers)
