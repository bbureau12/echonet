from __future__ import annotations

import time
import uuid
from dataclasses import dataclass
from typing import Optional

from .settings import settings


def _now_s() -> int:
    return int(time.time())


@dataclass
class Session:
    id: str
    target: str
    source_id: str
    room: Optional[str]
    last_ts: int


class SessionManager:
    def __init__(self, timeout_s: int):
        self.timeout_s = timeout_s
        self._by_source: dict[str, Session] = {}

    def get(self, source_id: str) -> Session | None:
        s = self._by_source.get(source_id)
        if not s:
            return None
        # expire lazily
        if _now_s() - s.last_ts > self.timeout_s:
            self._by_source.pop(source_id, None)
            return None
        return s

    def open(self, *, source_id: str, target: str, room: Optional[str], ts: int) -> Session:
        s = Session(id=f"sess-{uuid.uuid4().hex[:8]}", target=target, source_id=source_id, room=room, last_ts=ts)
        self._by_source[source_id] = s
        return s

    def touch(self, source_id: str, ts: int, room: Optional[str]) -> Session | None:
        s = self._by_source.get(source_id)
        if not s:
            return None
        s.last_ts = ts
        if room:
            s.room = room
        return s

    def end(self, source_id: str) -> None:
        self._by_source.pop(source_id, None)

    def all(self) -> list[Session]:
        # return only non-expired
        out = []
        for sid in list(self._by_source.keys()):
            s = self.get(sid)
            if s:
                out.append(s)
        return out


class PhraseRouter:
    def __init__(self, cancel_phrases: list[str]):
        self.cancel_phrases = [p.strip().lower() for p in cancel_phrases if p.strip()]

    def is_cancel(self, text: str) -> bool:
        t = text.lower()
        return any(p in t for p in self.cancel_phrases)

    def find_trigger(self, text: str, phrase_map: list[tuple[str, str]]) -> tuple[str, str] | None:
        """
        Returns (matched_phrase, target_name) using case-insensitive substring match.
        v0.1 is intentionally simple.
        """
        t = text.lower()
        for phrase, target in phrase_map:
            if phrase and phrase in t:
                return phrase, target
        return None

    def strip_trigger(self, text: str, matched_phrase: str) -> str:
        if not settings.forward_strip_trigger:
            return text
        t = text
        idx = t.lower().find(matched_phrase.lower())
        if idx < 0:
            return text
        # remove the matched phrase and common separators
        before = t[:idx]
        after = t[idx + len(matched_phrase):]
        out = (before + " " + after).strip()
        out = out.lstrip(" ,:-").strip()
        return out or text
