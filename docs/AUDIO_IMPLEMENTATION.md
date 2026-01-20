# Audio Device Management - Implementation Summary

## What Was Implemented

### 1. Audio Device Enumeration (`app/audio_io.py`)
- **`AudioDevice` dataclass**: Represents device info (index, name, channels, sample_rate, is_default)
- **`list_audio_devices()`**: Returns all available audio input devices
- **`get_default_device()`**: Returns the system's default audio input device
- **`record_once()`**: Records audio with device selection support
  - Takes `device_index` parameter (None = system default)
  - Runs in thread pool to avoid blocking async loop
  - Returns NumPy array of audio samples

### 2. Configuration (`app/settings.py`)
Added audio device settings:
```python
audio_device_index: int = 0  # Device to use (0 = first/default)
audio_sample_rate: int = 16000  # 16kHz for speech
audio_channels: int = 1  # Mono recording
```

### 3. State Management (`app/state.py`)
Added cache-based audio device tracking:
- **`get_audio_device_index()`**: Get current device from cache
- **`set_audio_device_index()`**: Update device in DB and cache
- No database overhead - reads from in-memory cache

### 4. API Endpoints (`app/main.py`)

#### GET /audio/devices
Returns list of all devices + currently selected one:
```json
{
  "devices": [
    {
      "index": 0,
      "name": "Microphone",
      "channels": 2,
      "sample_rate": 48000.0,
      "is_default": true
    }
  ],
  "current_index": 0
}
```

#### PUT /audio/device
Change the audio device:
```json
{
  "device_index": 1
}
```

### 5. Startup Device Selection (`app/main.py`)
Priority order:
1. **Cached selection** (from previous API call)
2. **Config file** (`ECHONET_AUDIO_DEVICE_INDEX`)
3. **System default** (from OS)
4. **First available** device

Logs available devices:
```
[INFO] Found 3 audio input devices:
[INFO]   [0] Microphone (Realtek) (DEFAULT)
[INFO]   [1] USB Microphone (Blue Yeti)
[INFO]   [2] Line In
[INFO] Using system default audio device: Microphone (index 0)
```

### 6. ASR Worker Integration (`app/asr_worker.py`)
- Receives device list and initial index at startup
- If multiple devices: monitors cache for changes each loop
- If single device: no overhead, uses constant index
- Passes device_index to `record_once()`

### 7. Data Models (`app/models.py`)
```python
class AudioDeviceInfo(BaseModel):
    index: int
    name: str
    channels: int
    sample_rate: float
    is_default: bool

class AudioDeviceList(BaseModel):
    devices: list[AudioDeviceInfo]
    current_index: int

class AudioDeviceSelection(BaseModel):
    device_index: int
```

## How It Works

### Startup Flow
```
1. Enumerate devices via sounddevice
2. Log all available input devices
3. Determine which device to use:
   - Check cache (from previous API selection)
   - Check .env (ECHONET_AUDIO_DEVICE_INDEX)
   - Use system default
   - Fall back to first device
4. Save selection to cache
5. Pass device list + index to ASR worker
```

### Runtime Device Change
```
1. API receives PUT /audio/device {device_index: N}
2. Validate N is in available devices
3. Update StateManager cache (no DB polling needed)
4. Update global variable
5. Worker detects change on next loop iteration
6. Next recording uses new device
```

### Worker Efficiency

**Single Device:**
- No cache checks
- Constant device index
- Zero overhead

**Multiple Devices:**
- Cache read once per loop (~50ms)
- In-memory lookup (microseconds)
- Change detection via simple integer comparison
- No database queries

## Environment Variables Added

```bash
# Audio device settings
ECHONET_AUDIO_DEVICE_INDEX=0  # 0 = first/default
ECHONET_AUDIO_SAMPLE_RATE=16000  # 16kHz for speech
ECHONET_AUDIO_CHANNELS=1  # Mono

# Event metadata
ECHONET_ECHONET_SOURCE_ID=microphone
ECHONET_ECHONET_ROOM=default
```

## Testing

Created `tests/test_audio_devices.py` with tests for:
- AudioDevice dataclass
- Device enumeration
- Default device detection
- StateManager integration
- record_once parameter passing

## Usage Examples

### Check Available Devices
```bash
curl http://localhost:8123/audio/devices -H "X-API-Key: dev-change-me"
```

### Switch to Device 1
```bash
curl -X PUT http://localhost:8123/audio/device \
  -H "Content-Type: application/json" \
  -H "X-API-Key: dev-change-me" \
  -d '{"device_index": 1}'
```

### Monitor Logs for Changes
```
[INFO] Audio device changed: 0 -> 1
```

## Performance Impact

- **Database reads**: Zero (cache-based)
- **Cache reads**: ~1 per loop iteration if multiple devices
- **Device change latency**: 2-3 seconds (next recording cycle)
- **Memory overhead**: ~1KB for device list

## Future Enhancements

- [ ] Hot-plug detection (device add/remove events)
- [ ] Audio level monitoring
- [ ] Device capability testing
- [ ] Automatic fallback on device failure
- [ ] Per-device configuration profiles
