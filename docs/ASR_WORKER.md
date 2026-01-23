# ASR Worker Architecture

## Overview

The ASR worker supports three operational modes with efficient state monitoring via in-memory caching.

## Modes

EchoNet operates as a state machine with three distinct modes:

```
┌──────────┐
│ INACTIVE │  ← Not recording (privacy/power saving)
└────┬─────┘
     │ ↕
┌────┴─────┐
│ TRIGGER  │  ← Recording with wake word detection
└────┬─────┘
     │ ↕
┌────┴─────┐
│  ACTIVE  │  ← Recording without filtering (routes all audio)
└──────────┘
```

All transitions are bi-directional via API.

### Inactive Mode
- **Purpose**: Privacy and power management
- **Behavior**: 
  - **No recording** - Microphone not accessed
  - **No transcription** - No CPU usage for ASR
  - **No routing** - No network traffic
  - Worker just sleeps in loop
- **Use Cases**:
  - Physical mute button pressed
  - Power saving mode (battery low)
  - Scheduled privacy hours (e.g., 10 PM - 7 AM)
  - Testing non-audio functionality
- **Related**: See [ADR 002](./adr/002-inactive-mode.md)

### Trigger Mode (Default)
- **Purpose**: Wake word detection
- **Behavior**: 
  - Records until silence detected (VAD)
  - Transcribes audio
  - Checks for registered wake word phrases
  - Only routes if wake word found
  - Discards audio without wake words
- **Use Cases**:
  - "Hey Alexa" style interaction
  - Default listening state
  - Waiting for user intent
- **Privacy**: Records and transcribes all audio, but only routes when wake word detected

### Active Mode
- **Purpose**: Continuous listening (e.g., during conversation)
- **Behavior**:
  - Records until silence detected (VAD)
  - Transcribes audio
  - Routes ALL transcriptions (no wake word check)
  - **Auto-resets to trigger mode** after completing recording
- **Use Cases**:
  - LLM asked a question, waiting for answer
  - Doorbell button pressed, waiting for command
  - Follow-up interaction without wake word
- **Auto-Reset**: Prevents staying in "route all audio" mode indefinitely
- **Related**: See [ADR 001](./adr/001-automatic-active-mode-reset.md)

## Mode Lifecycle

### Typical Interaction Flow

```
[System starts in TRIGGER mode]
    ↓
User: "Peter, what's the weather?"
    ↓ (wake word "Peter" detected)
[Routes to target, target requests ACTIVE mode]
    ↓
[Switches to ACTIVE mode]
    ↓
Target: "What city?"
    ↓
User: "Seattle"
    ↓ (routes without wake word)
[ACTIVE mode completes, auto-resets to TRIGGER]
    ↓
[Back in TRIGGER mode, listening for wake word]
```

### Privacy/Mute Flow

```
[User presses mute button]
    ↓
[API call: state=inactive]
    ↓
[INACTIVE mode - not recording]
    ↓
[User presses unmute button]
    ↓
[API call: state=trigger]
    ↓
[TRIGGER mode - listening for wake words]
```

## State Management

### Cache-Based Architecture
To avoid database polling overhead:

1. **In-Memory Cache**: `StateManager` maintains a dictionary cache of all settings
2. **Cache Loading**: Loaded once on first access from database
3. **Fast Reads**: Worker reads from cache (no DB query per loop iteration)
4. **Event Notification**: When API updates state via `PUT /state`:
   - Database is updated
   - Cache is updated
   - `asyncio.Event` is triggered (optional - worker can poll cache)

### Performance Benefits
- **Before**: Database read every ~50ms = ~20 queries/second
- **After**: In-memory dictionary lookup = negligible overhead
- **API Updates**: Single database write + cache update

## Configuration

Environment variables control ASR behavior:

```bash
# Echonet event metadata
ECHONET_SOURCE_ID=microphone
ECHONET_ROOM=living-room

# Initial mode on startup
ECHONET_INITIAL_LISTEN_MODE=trigger  # or "active" or "inactive"

# Whisper model configuration
ECHONET_WHISPER_MODEL=base  # tiny, base, small, medium, large
ECHONET_WHISPER_DEVICE=cpu  # cpu or cuda
ECHONET_WHISPER_COMPUTE_TYPE=int8  # int8 (cpu) or float16 (gpu)
ECHONET_WHISPER_LANGUAGE=en  # language code or "auto"
```

## Flow Diagram

```
┌─────────────────────────────────────────────────────────┐
│                    ASR Worker Loop                      │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
              ┌───────────────────────────────┐
              │   Read mode from cache        │ ◄── Fast, no DB hit
              │ (inactive/trigger/active)     │
              └───────────┬───────────────────┘
                          │
         ┌────────────────┼────────────────┐
         │                │                │
         ▼                ▼                ▼
 ┌──────────────┐  ┌──────────────┐  ┌──────────────┐
 │   Inactive   │  │   Trigger    │  │    Active    │
 │   (muted)    │  │ (wake word)  │  │ (continuous) │
 └──────────────┘  └──────────────┘  └──────────────┘
         │                │                │
         ▼                ▼                ▼
 ┌──────────────┐  ┌──────────────┐  ┌──────────────┐
 │ Sleep 0.5s   │  │ Record audio │  │ Record audio │
 │ (no mic      │  │ until VAD    │  │ until VAD    │
 │  access)     │  │ detects      │  │ detects      │
 └──────────────┘  │ silence      │  │ silence      │
                   └──────┬───────┘  └──────┬───────┘
                          │                 │
                          ▼                 ▼
                   ┌──────────────┐  ┌──────────────┐
                   │ Transcribe   │  │ Transcribe   │
                   └──────┬───────┘  └──────┬───────┘
                          │                 │
                          ▼                 ▼
                   ┌──────────────┐  ┌──────────────┐
                   │ Check if     │  │ Send all     │
                   │ wake word in │  │ non-empty    │
                   │ phrase map   │  │ text         │
                   └──────┬───────┘  └──────┬───────┘
                          │                 │
                   ┌──────┴──────┐          │
                   │ If detected │          │
                   └──────┬──────┘          │
                          │                 │
                          ▼                 ▼
                   ┌────────────────────────────┐
                   │   post_text_event()        │
                   │   to Echonet API           │
                   └────────────────────────────┘
                                  │
                                  ▼
                          ┌──────────────────┐
                          │ Auto-reset to    │
                          │ TRIGGER mode     │
                          │ (active only)    │
                          └──────────────────┘


┌─────────────────────────────────────────────────────────┐
│              State Update via API                       │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
              ┌───────────────────────┐
              │ PUT /state            │
              │ (mode=active/trigger) │
              └───────────┬───────────┘
                          │
                          ▼
              ┌───────────────────────┐
              │ StateManager.set()    │
              ├───────────────────────┤
              │ 1. Write to DB        │
              │ 2. Update cache       │
              │ 3. Trigger event      │
              └───────────────────────┘
                          │
                          ▼
              ┌───────────────────────┐
              │ Worker reads cache    │
              │ on next iteration     │
              └───────────────────────┘
```

## API Integration

The `PUT /state` endpoint switches modes:

```bash
# Mute (stop recording)
curl -X PUT http://localhost:8123/state \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-key" \
  -d '{
    "target": "system",
    "source": "mute_button", 
    "state": "inactive",
    "reason": "User pressed mute button"
  }'

# Unmute (resume listening for wake words)
curl -X PUT http://localhost:8123/state \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-key" \
  -d '{
    "target": "system",
    "source": "mute_button",
    "state": "trigger", 
    "reason": "User pressed unmute button"
  }'

# Switch to active mode (e.g., after wake word detected)
curl -X PUT http://localhost:8123/state \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-key" \
  -d '{
    "target": "llm_assistant",
    "source": "llm_response", 
    "state": "active",
    "reason": "User started conversation"
  }'

# Return to trigger mode (manual, or happens automatically)
curl -X PUT http://localhost:8123/state \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-key" \
  -d '{
    "target": "llm_assistant",
    "source": "conversation_end",
    "state": "trigger", 
    "reason": "Conversation completed"
  }'
```

## Implementation Details

### StateManager Cache
```python
# In-memory cache loaded once
self._cache: dict[str, str] = {}

# Fast read (no DB query)
def get_value(self, name: str, default: Optional[str] = None) -> str:
    self._ensure_cache_loaded()
    return self._cache.get(name, default)

# Write updates both DB and cache
def set(self, name: str, value: str, ...):
    # ... update database ...
    self._cache[name] = value  # Update cache
```

### Worker Loop
```python
async def run_asr_worker(state_manager, registry, stop_event):
    while not stop_event.is_set():
        # Fast cache read (not DB query)
        mode = state_manager.get_listen_mode()
        
        if mode == "inactive":
            await asyncio.sleep(0.5)  # No recording
        elif mode == "trigger":
            await _handle_trigger_mode(...)
        else:  # active
            await _handle_active_mode(...)
```

## Future Enhancements

- [ ] Voice Activity Detection (VAD) for better silence detection
- [ ] Configurable recording durations per mode
- [ ] Wake word confidence thresholds
- [ ] Multi-language wake word support
- [ ] Streaming transcription for lower latency
