from __future__ import annotations

import logging
import uuid

import httpx

from .models import EchonetTextOut
from .settings import settings

log = logging.getLogger("echonet.forwarder")


class TargetForwarder:
    def __init__(self):
        self.client = httpx.AsyncClient(timeout=settings.http_timeout_s)

    async def close(self) -> None:
        await self.client.aclose()

    async def forward_text(self, *, listen_url: str, payload: EchonetTextOut) -> bool:
        try:
            r = await self.client.post(listen_url, json=payload.model_dump())
            if 200 <= r.status_code < 300:
                return True
            log.warning("Forward failed %s -> %s (%s): %s", payload.source_id, listen_url, r.status_code, r.text)
            return False
        except Exception as e:
            log.warning("Forward exception %s -> %s: %s", payload.source_id, listen_url, e)
            return False


def make_event_id() -> str:
    return f"en-{uuid.uuid4().hex[:12]}"
