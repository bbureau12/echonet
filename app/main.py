from __future__ import annotations

import asyncio
import logging

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse

from app.asr_worker import run_asr_worker
from app.audio_io import list_audio_devices, get_default_device, AudioDevice

from .models import (
    RouteDecision, SessionState, TargetRegistration, TextIn, EchonetTextOut, StateUpdate,
    AudioDeviceInfo, AudioDeviceList, AudioDeviceSelection
)
from .registry import Target, TargetRegistryRepository
from .router import PhraseRouter, SessionManager
from .security import require_api_key, require_admin_key
from .settings import settings
from .forwarder import TargetForwarder, make_event_id
from .migrations import run_migrations
from .state import StateManager
from .discovery import DiscoveryService

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("echonet")

app = FastAPI(title="Echonet", version="0.1.0")

# Run database migrations before initializing registry
log.info("Running database migrations...")
run_migrations(settings.db_path)

registry = TargetRegistryRepository(db_path=settings.db_path)
state = StateManager(db_path=settings.db_path)
sessions = SessionManager(timeout_s=settings.session_timeout_s)
phrase_router = PhraseRouter(cancel_phrases=settings.cancel_phrases.split(","))
forwarder = TargetForwarder()

# mDNS Discovery service
discovery: DiscoveryService | None = None

# Audio devices (populated at startup)
audio_devices: list[AudioDevice] = []
selected_device_index: int = 0


@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    resp = require_api_key(request)
    if resp is not None:
        return resp
    return await call_next(request)
    app.state.runtime = state

@app.on_event("startup")
async def startup():
    global discovery, audio_devices, selected_device_index
    
    # Enumerate audio devices
    log.info("Enumerating audio input devices...")
    try:
        audio_devices = list_audio_devices()
        
        if not audio_devices:
            log.warning("No audio input devices found!")
        elif len(audio_devices) == 1:
            log.info(f"Found 1 audio device: {audio_devices[0].name}")
            selected_device_index = audio_devices[0].index
        else:
            log.info(f"Found {len(audio_devices)} audio input devices:")
            for device in audio_devices:
                default_marker = " (DEFAULT)" if device.is_default else ""
                log.info(f"  [{device.index}] {device.name}{default_marker}")
            
            # Get device from cache, fallback to config, then default
            cached_index = state.get_audio_device_index()
            
            # Check if cached index is valid
            if any(d.index == cached_index for d in audio_devices):
                selected_device_index = cached_index
                log.info(f"Using cached audio device index: {selected_device_index}")
            else:
                # Use config default or system default
                if settings.audio_device_index == 0:
                    # Try to find system default
                    default_device = get_default_device()
                    if default_device:
                        selected_device_index = default_device.index
                        log.info(f"Using system default audio device: {default_device.name} (index {selected_device_index})")
                    else:
                        selected_device_index = audio_devices[0].index
                        log.info(f"Using first available audio device: {audio_devices[0].name} (index {selected_device_index})")
                else:
                    # Use configured index if valid
                    if any(d.index == settings.audio_device_index for d in audio_devices):
                        selected_device_index = settings.audio_device_index
                        log.info(f"Using configured audio device index: {selected_device_index}")
                    else:
                        log.warning(f"Configured device index {settings.audio_device_index} not found, using first device")
                        selected_device_index = audio_devices[0].index
                
                # Save to cache
                state.set_audio_device_index(
                    selected_device_index,
                    source="startup",
                    reason="Initial device selection"
                )
    except Exception as e:
        log.error(f"Failed to enumerate audio devices: {e}")
        audio_devices = []
        selected_device_index = 0
    
    # Load registered targets and initialize phrase router
    log.info("Loading registered targets...")
    targets = registry.all()
    if targets:
        log.info(f"Found {len(targets)} registered target(s):")
        for target in targets:
            log.info(f"  - {target.name}: {len(target.phrases)} phrase(s)")
    else:
        log.info("No targets registered yet. Use POST /register to add targets.")
    
    # Initialize state to configured default mode
    current_mode = state.get_listen_mode()
    if current_mode != settings.initial_listen_mode:
        log.info(f"Setting initial listen mode to '{settings.initial_listen_mode}'")
        state.set_listen_mode(
            mode=settings.initial_listen_mode,
            source="startup",
            reason=f"Application startup - configured default mode"
        )
    else:
        log.info(f"Listen mode already set to '{current_mode}'")
    
    # Start mDNS discovery if enabled
    if settings.discovery_enabled:
        log.info("Starting mDNS discovery service...")
        discovery = DiscoveryService(
            instance_name=settings.discovery_name,
            host=settings.discovery_host,
            port=settings.port,
            zone=settings.discovery_zone,
            subzone=settings.discovery_subzone,
        )
        discovery.start()
    else:
        log.info("mDNS discovery disabled")
    
    # Start ASR worker
    log.info("Starting ASR worker...")
    app.state.asr_stop_event = asyncio.Event()
    app.state.asr_task = asyncio.create_task(
        run_asr_worker(state, registry, audio_devices, selected_device_index, app.state.asr_stop_event)
    )

@app.on_event("shutdown")
async def _shutdown():
    # Stop discovery
    if discovery:
        discovery.stop()
    
    # Stop ASR worker
    stop_event = getattr(app.state, "asr_stop_event", None)
    if stop_event:
        stop_event.set()
    
    task = getattr(app.state, "asr_task", None)
    if task:
        task.cancel()
    
    await forwarder.close()


@app.get("/health")
async def health():
    return {"ok": True, "service": "echonet", "version": "0.1.0"}


@app.get("/handshake")
async def handshake():
    """
    Returns discovery and configuration information.
    Useful for LLMs and other services to verify connectivity and understand capabilities.
    """
    return {
        "ok": True,
        "discovery": {
            "enabled": settings.discovery_enabled,
            "instance_name": settings.discovery_name,
            "host": settings.discovery_host,
            "zone": settings.discovery_zone,
            "subzone": settings.discovery_subzone,
            "port": settings.port,
        },
        "capabilities": {
            "asr": True,
            "target_routing": True,
            "session_management": True,
            "state_tracking": True,
        },
        "config": {
            "session_timeout_s": settings.session_timeout_s,
            "cancel_phrases": settings.cancel_phrases.split(","),
        },
        "version": "0.1.0",
    }



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


@app.get("/state")
async def get_state():
    """Get current application state/settings."""
    settings_list = state.all()
    return {
        "ok": True,
        "settings": [
            {
                "name": s.name,
                "value": s.value,
                "updated_at": s.updated_at,
                "description": s.description
            }
            for s in settings_list
        ],
        "listen_mode": state.get_listen_mode()
    }


@app.get("/state/history")
async def get_state_history(name: str = None, limit: int = 50):
    """Get state change history."""
    if limit > 500:
        limit = 500  # Cap at 500 to prevent excessive queries
    
    changes = state.get_history(name=name, limit=limit)
    return {
        "ok": True,
        "count": len(changes),
        "changes": [
            {
                "id": c.id,
                "name": c.name,
                "old_value": c.old_value,
                "new_value": c.new_value,
                "changed_at": c.changed_at,
                "source": c.source,
                "reason": c.reason
            }
            for c in changes
        ]
    }


@app.put("/state")
async def update_state(request: Request, update: StateUpdate):
    """
    Update the listen mode state.
    
    Validates that the target exists before updating state.
    Requires admin key if configured.
    """
    # Optional admin key
    resp = require_admin_key(request)
    if resp is not None:
        return resp
    
    # Verify target exists
    target = registry.get(update.target)
    if target is None:
        return JSONResponse(
            status_code=404,
            content={
                "ok": False,
                "error": f"Target '{update.target}' not found. Register the target first."
            }
        )
    
    # Update the state
    try:
        # Build a descriptive reason if not provided
        reason = update.reason
        if not reason:
            reason = f"State change requested by {update.target}"
        
        state.set_listen_mode(
            mode=update.state,
            source=f"{update.source}:{update.target}",
            reason=reason
        )
        
        return {
            "ok": True,
            "listen_mode": update.state,
            "target": update.target,
            "source": update.source,
            "message": f"Listen mode set to '{update.state}' by target '{update.target}'"
        }
    except ValueError as e:
        return JSONResponse(
            status_code=400,
            content={"ok": False, "error": str(e)}
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


# ========== Audio Device Management Endpoints ==========

@app.get("/audio/devices", response_model=AudioDeviceList, tags=["audio"])
async def get_audio_devices():
    """
    Get a list of all available audio input devices and the currently selected one.
    """
    current_index = state.get_audio_device_index()
    
    return AudioDeviceList(
        devices=[
            AudioDeviceInfo(
                index=device.index,
                name=device.name,
                channels=device.channels,
                sample_rate=device.sample_rate,
                is_default=device.is_default
            )
            for device in audio_devices
        ],
        current_index=current_index
    )


@app.put("/audio/device", tags=["audio"])
async def set_audio_device(selection: AudioDeviceSelection):
    """
    Set the audio input device to use for recording.
    The change takes effect on the next recording cycle.
    """
    # Validate device index exists
    if not any(d.index == selection.device_index for d in audio_devices):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid device index {selection.device_index}. Available: {[d.index for d in audio_devices]}"
        )
    
    # Update cache
    state.set_audio_device_index(
        selection.device_index,
        source="api",
        reason="User selected audio device"
    )
    
    # Update global variable for worker
    global selected_device_index
    selected_device_index = selection.device_index
    
    device_name = next((d.name for d in audio_devices if d.index == selection.device_index), "Unknown")
    
    return {
        "status": "ok",
        "device_index": selection.device_index,
        "device_name": device_name,
        "message": f"Audio device changed to: {device_name}"
    }
