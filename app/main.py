from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from .models import RouteDecision, SessionState, TargetRegistration, TextIn, EchonetTextOut
from .registry import Target, TargetRegistry
from .router import PhraseRouter, SessionManager
from .security import require_api_key, require_admin_key
from .settings import settings
from .forwarder import TargetForwarder, make_event_id
from .migrations import run_migrations

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("echonet")

app = FastAPI(title="Echonet", version="0.1.0")

# Run database migrations before initializing registry
log.info("Running database migrations...")
run_migrations(settings.db_path)

registry = TargetRegistry(db_path=settings.db_path)
sessions = SessionManager(timeout_s=settings.session_timeout_s)
phrase_router = PhraseRouter(cancel_phrases=settings.cancel_phrases.split(","))
forwarder = TargetForwarder()


@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    resp = require_api_key(request)
    if resp is not None:
        return resp
    return await call_next(request)


@app.on_event("shutdown")
async def _shutdown():
    await forwarder.close()


@app.get("/health")
async def health():
    return {"ok": True, "service": "echonet", "version": "0.1.0"}


@app.post("/register")
async def register_target(request: Request, reg: TargetRegistration):
    # Optional admin key for registration
    resp = require_admin_key(request)
    if resp is not None:
        return resp

    t = Target(name=reg.name.strip(), base_url=reg.base_url.strip(), phrases=reg.phrases)
    registry.upsert(t)
    return {"ok": True, "registered": t.name, "listen_url": t.listen_url, "phrases": t.phrases}


@app.get("/targets")
async def list_targets():
    return {
        "ok": True,
        "targets": [
            {"name": t.name, "base_url": t.base_url, "listen_url": t.listen_url, "phrases": t.phrases}
            for t in registry.all()
        ],
    }


@app.delete("/targets/{name}")
async def delete_target(request: Request, name: str):
    # Optional admin key for deletion
    resp = require_admin_key(request)
    if resp is not None:
        return resp
    
    deleted = registry.delete(name)
    if deleted:
        return {"ok": True, "deleted": name}
    else:
        return JSONResponse(
            status_code=404,
            content={"ok": False, "error": f"Target '{name}' not found"}
        )


@app.get("/sessions")
async def list_sessions():
    out = []
    now = __import__("time").time()
    for s in sessions.all():
        expires_in = max(0, settings.session_timeout_s - int(now) + s.last_ts)
        out.append(
            {
                "id": s.id,
                "target": s.target,
                "source_id": s.source_id,
                "room": s.room,
                "last_ts": s.last_ts,
                "expires_in_s": expires_in,
            }
        )
    return {"ok": True, "sessions": out}


@app.post("/sessions/{source_id}/end")
async def end_session(source_id: str):
    sessions.end(source_id)
    return {"ok": True, "ended": source_id}


@app.post("/text", response_model=RouteDecision)
async def ingest_text(inp: TextIn):
    # 0) Cancel ends any session
    if phrase_router.is_cancel(inp.text):
        sessions.end(inp.source_id)
        return RouteDecision(
            handled=True,
            mode="session_end",
            routed_to=None,
            forwarded=False,
            reason="cancel_phrase",
        )

    # 1) If trigger matches, open/switch session to that target
    phrase_map = registry.phrase_map()
    trig = phrase_router.find_trigger(inp.text, phrase_map)

    active = sessions.get(inp.source_id)

    if trig:
        matched_phrase, target_name = trig
        if not registry.get(target_name):
            return RouteDecision(handled=False, mode="idle", reason="trigger_target_missing")

        # switch or open
        if active and active.target != target_name:
            active = sessions.open(source_id=inp.source_id, target=target_name, room=inp.room, ts=inp.ts)
            mode = "session_switch"
        else:
            active = sessions.open(source_id=inp.source_id, target=target_name, room=inp.room, ts=inp.ts)
            mode = "session_open"

        text_to_send = phrase_router.strip_trigger(inp.text, matched_phrase)
        listen_url = registry.get(target_name).listen_url

        payload = EchonetTextOut(
            event_id=make_event_id(),
            ts=inp.ts,
            source_id=inp.source_id,
            room=inp.room,
            session_id=active.id,
            mode="triggered",
            text=text_to_send,
            confidence=inp.confidence,
        )

        forwarded = await forwarder.forward_text(listen_url=listen_url, payload=payload)

        return RouteDecision(
            handled=True,
            routed_to=target_name,
            mode=mode,
            session=SessionState(
                id=active.id,
                target=active.target,
                source_id=active.source_id,
                room=active.room,
                last_ts=active.last_ts,
                expires_in_s=settings.session_timeout_s,
            ),
            forwarded=forwarded,
            reason=f"trigger_phrase:{matched_phrase}",
        )

    # 2) If session exists, forward to session target (open listen)
    if active:
        sessions.touch(inp.source_id, ts=inp.ts, room=inp.room)
        t = registry.get(active.target)
        if not t:
            # target disappeared; end session
            sessions.end(inp.source_id)
            return RouteDecision(handled=False, mode="session_end", reason="target_unregistered")

        payload = EchonetTextOut(
            event_id=make_event_id(),
            ts=inp.ts,
            source_id=inp.source_id,
            room=inp.room or active.room,
            session_id=active.id,
            mode="open_listen",
            text=inp.text,
            confidence=inp.confidence,
        )
        forwarded = await forwarder.forward_text(listen_url=t.listen_url, payload=payload)

        return RouteDecision(
            handled=True,
            routed_to=active.target,
            mode="session_continue",
            session=SessionState(
                id=active.id,
                target=active.target,
                source_id=active.source_id,
                room=inp.room or active.room,
                last_ts=inp.ts,
                expires_in_s=settings.session_timeout_s,
            ),
            forwarded=forwarded,
            reason="session_active",
        )

    # 3) No trigger, no session => idle
    return RouteDecision(handled=False, mode="idle", reason="no_trigger_no_session")
