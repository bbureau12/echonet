# Configuration API

## Overview

EchoNet provides a runtime configuration API for managing optional features and settings. Configuration is stored in the database and can be updated via API without restarting the service.

## Endpoints

### GET /config

Get all configuration settings.

**Response**:
```json
{
  "settings": {
    "enable_preroll_buffer": {
      "key": "enable_preroll_buffer",
      "value": "false",
      "type": "bool",
      "description": "Enable pre-roll audio buffering (capture audio before trigger)",
      "updated_at": "2026-01-23T10:30:00Z"
    },
    "preroll_buffer_seconds": {
      "key": "preroll_buffer_seconds",
      "value": "2.0",
      "type": "float",
      "description": "Seconds of audio to buffer before trigger event",
      "updated_at": "2026-01-23T10:30:00Z"
    }
  }
}
```

### GET /config/{key}

Get a specific configuration setting.

**Example**:
```bash
curl http://localhost:8123/config/enable_preroll_buffer \
  -H "X-API-Key: your-key"
```

**Response**:
```json
{
  "key": "enable_preroll_buffer",
  "value": "false",
  "type": "bool",
  "description": "Enable pre-roll audio buffering (capture audio before trigger)",
  "updated_at": "2026-01-23T10:30:00Z"
}
```

### PUT /config/{key}

Update a configuration setting.

**Example** - Enable pre-roll buffering:
```bash
curl -X PUT http://localhost:8123/config/enable_preroll_buffer \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-admin-key" \
  -d '{"value": "true"}'
```

**Example** - Set buffer duration:
```bash
curl -X PUT http://localhost:8123/config/preroll_buffer_seconds \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-admin-key" \
  -d '{"value": "3.0"}'
```

**Response**:
```json
{
  "key": "enable_preroll_buffer",
  "value": "true",
  "type": "bool",
  "description": "Enable pre-roll audio buffering (capture audio before trigger)",
  "updated_at": "2026-01-23T15:45:00Z"
}
```

## Configuration Settings

### enable_preroll_buffer

- **Type**: `bool`
- **Default**: `false`
- **Values**: `"true"` or `"false"`
- **Description**: Enable pre-roll audio buffering to capture audio before a trigger event

When enabled, the system maintains a rolling buffer of recent audio. When a trigger event occurs (e.g., button press), the buffered audio is prepended to the recording, capturing what was said *before* the button was pressed.

**Use Cases**:
- Doorbell button: User says "package delivery" then presses button
- Push-to-talk: User starts speaking before pressing button
- Hardware triggers: Capture audio before physical trigger activates

### preroll_buffer_seconds

- **Type**: `float`
- **Default**: `2.0`
- **Range**: `0.5` - `10.0` (recommended)
- **Description**: Duration of audio to buffer before trigger event

Controls how much audio history to maintain. Larger values use more memory but capture more context.

**Examples**:
- `1.0` - Good for quick button presses
- `2.0` - Default, balances memory and utility
- `5.0` - Longer context, useful for complex scenarios

## Type Validation

The API validates values against their declared types:

- **bool**: Must be `"true"` or `"false"` (case-insensitive)
- **int**: Must be a valid integer string (e.g., `"42"`)
- **float**: Must be a valid float string (e.g., `"3.14"`)
- **str**: Any string value

Invalid values return a `400 Bad Request` error.

## Using Pre-Roll Buffering

### Basic Setup

1. **Enable pre-roll buffering**:
```bash
curl -X PUT http://localhost:8123/config/enable_preroll_buffer \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-admin-key" \
  -d '{"value": "true"}'
```

2. **Set buffer duration** (optional):
```bash
curl -X PUT http://localhost:8123/config/preroll_buffer_seconds \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-admin-key" \
  -d '{"value": "3.0"}'
```

### Example: Doorbell with Pre-Roll

**Scenario**: User says "There's a package at the door" *before* pressing the doorbell button.

**Without pre-roll**: Only captures audio *after* button press, misses the command.

**With pre-roll**:
```python
from app.audio_io import RingBuffer, record_until_silence

# Create ring buffer (done once at startup if enabled)
buffer = RingBuffer(duration_seconds=2.0, sample_rate=16000, channels=1)

# Background task: Continuously fill buffer (in trigger mode)
while in_trigger_mode:
    chunk = await record_chunk(duration=0.1)  # 100ms chunks
    buffer.add_chunk(chunk)

# When button pressed:
# 1. Switch to active mode
await set_listen_mode("active")

# 2. Record with pre-roll buffer
audio = await record_until_silence(
    device_index=0,
    preroll_buffer=buffer  # Prepends buffered audio
)

# 3. Transcribe (includes pre-roll audio)
text = await transcribe_audio(audio)
# Result: "There's a package at the door [button press] yes"
```

## Implementation Notes

### Ring Buffer

The `RingBuffer` class (`app/audio_io.py`) manages the pre-roll buffer:

```python
from app.audio_io import RingBuffer

# Create buffer for 2 seconds of audio
buffer = RingBuffer(
    duration_seconds=2.0,
    sample_rate=16000,
    channels=1
)

# Add audio chunks (automatically drops oldest when full)
buffer.add_chunk(audio_chunk)

# Get buffered audio
buffered = buffer.get_buffered_audio()  # Returns numpy array

# Check buffer state
duration = buffer.get_duration()  # Seconds of buffered audio
is_full = buffer.is_full()  # True when >= target duration

# Clear buffer
buffer.clear()
```

### Integration with Recording

The `record_until_silence()` function accepts an optional `preroll_buffer` parameter:

```python
audio = await record_until_silence(
    device_index=0,
    sample_rate=16000,
    channels=1,
    preroll_buffer=buffer  # Optional: prepend buffered audio
)
```

When provided, the buffered audio is prepended to the recording, creating a seamless capture that includes audio from before the trigger event.

## Future Enhancements

- [ ] Automatic buffer management based on mode
- [ ] API to query buffer status
- [ ] Configurable chunk size for buffer
- [ ] Memory usage reporting
- [ ] Buffer persistence across mode changes

## Related Documentation

- [State Machine Reference](./STATE_MACHINE.md) - Mode system (inactive/trigger/active)
- [ASR Worker Architecture](./ASR_WORKER.md) - Audio processing flow
- [Audio Implementation](./AUDIO_IMPLEMENTATION.md) - Low-level audio details
