from __future__ import annotations

from typing import Literal, Optional
from pydantic import BaseModel, Field


class TargetRegistration(BaseModel):
    name: str = Field(..., min_length=1, max_length=32, description="Unique target name, e.g. 'astraea'")
    base_url: str = Field(..., min_length=4, description="Base URL, e.g. http://astraea.local:9001")
    phrases: list[str] = Field(default_factory=list, description="Trigger phrases for session open/switch")


class TextIn(BaseModel):
    source_id: str = Field(..., min_length=1, max_length=64)
    room: Optional[str] = Field(default=None, max_length=64)
    ts: int = Field(..., description="Unix timestamp (seconds)")
    text: str = Field(..., min_length=1, max_length=500)
    confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0)


class SessionState(BaseModel):
    id: str
    target: str
    source_id: str
    room: Optional[str] = None
    last_ts: int
    expires_in_s: int


class RouteDecision(BaseModel):
    handled: bool
    routed_to: Optional[str] = None
    mode: Literal["idle", "dispatch_once", "session_open", "session_continue", "session_end", "session_switch"] = "idle"
    session: Optional[SessionState] = None
    forwarded: bool = False
    reason: Optional[str] = None


class EchonetTextOut(BaseModel):
    event_id: str
    ts: int
    source_id: str
    room: Optional[str] = None
    session_id: Optional[str] = None
    mode: Literal["triggered", "open_listen"] = "triggered"
    text: str
    confidence: Optional[float] = None
