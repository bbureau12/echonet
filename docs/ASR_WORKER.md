# ASR Worker Architecture

## Overview

The ASR worker supports two operational modes with efficient state monitoring via in-memory caching.

## Modes

### Trigger Mode
- **Purpose**: Wake word detection
- **Behavior**: 
  - Records short 2-second audio clips
  - Transcribes and checks for registered target phrases
  - Only sends transcription if wake word is detected
  - Conserves resources when idle

### Active Mode
- **Purpose**: Continuous listening (e.g., during LLM conversation)
- **Behavior**:
  - Records longer 3-second audio clips
  - Transcribes all audio
  - Sends all non-empty transcriptions
  - Used when user is actively interacting

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
ECHONET_INITIAL_LISTEN_MODE=trigger  # or "active"

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
              ┌───────────────────────┐
              │ Read mode from cache  │ ◄── Fast, no DB hit
              │ (trigger or active)   │
              └───────────┬───────────┘
                          │
                ┌─────────┴─────────┐
                │                   │
                ▼                   ▼
    ┌──────────────────┐   ┌──────────────────┐
    │  Trigger Mode    │   │   Active Mode    │
    │ (wake word)      │   │ (continuous)     │
    └──────────────────┘   └──────────────────┘
                │                   │
                ▼                   ▼
        ┌──────────────┐    ┌──────────────┐
        │ Record 2 sec │    │ Record 3 sec │
        └──────┬───────┘    └──────┬───────┘
               │                   │
               ▼                   ▼
        ┌──────────────┐    ┌──────────────┐
        │ Transcribe   │    │ Transcribe   │
        └──────┬───────┘    └──────┬───────┘
               │                   │
               ▼                   ▼
        ┌──────────────┐    ┌──────────────┐
        │ Check if     │    │ Send all     │
        │ wake word in │    │ non-empty    │
        │ phrase map   │    │ text         │
        └──────┬───────┘    └──────┬───────┘
               │                   │
        ┌──────┴──────┐            │
        │ If detected │            │
        └──────┬──────┘            │
               │                   │
               ▼                   ▼
        ┌────────────────────────────┐
        │   post_text_event()        │
        │   to Echonet API           │
        └────────────────────────────┘


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
# Switch to active mode
curl -X PUT http://localhost:8123/state \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-key" \
  -d '{
    "target": "llm_assistant",
    "source": "llm_response", 
    "state": "active",
    "reason": "User started conversation"
  }'

# Return to trigger mode
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
        
        if mode == "trigger":
            await _handle_trigger_mode(...)
        else:
            await _handle_active_mode(...)
```

## Future Enhancements

- [ ] Voice Activity Detection (VAD) for better silence detection
- [ ] Configurable recording durations per mode
- [ ] Wake word confidence thresholds
- [ ] Multi-language wake word support
- [ ] Streaming transcription for lower latency
