# Audio Device Management

## Overview

Echonet supports multiple audio input devices with runtime selection and configuration through both environment variables and REST API.

## Startup Device Selection

On startup, Echonet follows this priority order:

1. **Cached Selection**: If a device was previously selected via API, use that
2. **Environment Config**: Use `ECHONET_AUDIO_DEVICE_INDEX` if set and valid
3. **System Default**: Use the operating system's default audio input device
4. **First Available**: Use the first device in the enumeration list

### Startup Logs

```
[INFO] Enumerating audio input devices...
[INFO] Found 3 audio input devices:
[INFO]   [0] Microphone (Realtek High Definition Audio) (DEFAULT)
[INFO]   [1] USB Microphone (Blue Yeti)
[INFO]   [2] Line In (Realtek High Definition Audio)
[INFO] Using system default audio device: Microphone (index 0)
```

## Configuration

### Environment Variables

```bash
# Device index (0 = use system default or first device)
ECHONET_AUDIO_DEVICE_INDEX=0

# Audio quality settings
ECHONET_AUDIO_SAMPLE_RATE=16000  # 16kHz optimal for speech
ECHONET_AUDIO_CHANNELS=1  # 1=mono, 2=stereo
```

### Runtime Device Selection

The selected device is stored in the cache and persists across API calls within the same session.

## API Endpoints

### GET /audio/devices

Get a list of all available audio input devices and the currently selected one.

**Response:**
```json
{
  "devices": [
    {
      "index": 0,
      "name": "Microphone (Realtek High Definition Audio)",
      "channels": 2,
      "sample_rate": 48000.0,
      "is_default": true
    },
    {
      "index": 1,
      "name": "USB Microphone (Blue Yeti)",
      "channels": 2,
      "sample_rate": 48000.0,
      "is_default": false
    }
  ],
  "current_index": 0
}
```

### PUT /audio/device

Change the audio input device used for recording.

**Request:**
```json
{
  "device_index": 1
}
```

**Response:**
```json
{
  "status": "ok",
  "device_index": 1,
  "device_name": "USB Microphone (Blue Yeti)",
  "message": "Audio device changed to: USB Microphone (Blue Yeti)"
}
```

**Error Response (Invalid Index):**
```json
{
  "detail": "Invalid device index 5. Available: [0, 1, 2]"
}
```

## Worker Integration

The ASR worker receives:
- List of all available audio devices at startup
- Initial device index from cache/config/default
- Monitors cache for device changes (if multiple devices available)

### Device Selection Flow

```
┌─────────────────────────────────────────────────────────┐
│                    Startup                              │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
              ┌───────────────────────┐
              │ Enumerate audio       │
              │ devices via sounddevice│
              └───────────┬───────────┘
                          │
                ┌─────────┴─────────┐
                │ Multiple devices? │
                └─────────┬─────────┘
                          │
                ┌─────────┴─────────┐
                │                   │
          YES   ▼                   ▼   NO
    ┌────────────────────┐   ┌────────────────┐
    │ Check cache        │   │ Use only       │
    │ Check config       │   │ device         │
    │ Use default        │   │                │
    └────────┬───────────┘   └────────────────┘
             │
             ▼
    ┌────────────────────┐
    │ Save to cache      │
    └────────┬───────────┘
             │
             ▼
    ┌────────────────────┐
    │ Pass to ASR worker │
    └────────────────────┘


┌─────────────────────────────────────────────────────────┐
│              Runtime Device Change                       │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
              ┌───────────────────────┐
              │ PUT /audio/device     │
              │ {device_index: 1}     │
              └───────────┬───────────┘
                          │
                          ▼
              ┌───────────────────────┐
              │ Validate index exists │
              └───────────┬───────────┘
                          │
                          ▼
              ┌───────────────────────┐
              │ StateManager.set()    │
              │ - Update DB           │
              │ - Update cache        │
              └───────────┬───────────┘
                          │
                          ▼
              ┌───────────────────────┐
              │ Update global var     │
              │ (for new workers)     │
              └───────────┬───────────┘
                          │
                          ▼
              ┌───────────────────────┐
              │ Worker reads cache    │
              │ on next iteration     │
              │ (if multiple devices) │
              └───────────────────────┘
```

## Implementation Details

### Audio Device Enumeration

```python
from app.audio_io import list_audio_devices, get_default_device

# Get all input devices
devices = list_audio_devices()

# Get system default
default = get_default_device()
```

### Worker Device Monitoring

```python
# In worker loop
if len(audio_devices) > 1:
    cached_device = state_manager.get_audio_device_index()
    if cached_device != device_index:
        log.info(f"Audio device changed: {device_index} -> {cached_device}")
        device_index = cached_device

# Use device for recording
audio = await record_once(
    seconds=2.0,
    device_index=device_index,
    sample_rate=settings.audio_sample_rate,
    channels=settings.audio_channels
)
```

## Performance Considerations

### Single Device
- **No overhead**: Device index is constant, no cache checks
- Worker uses the same device throughout runtime

### Multiple Devices
- **Minimal overhead**: Cache read once per loop iteration (~50ms)
- No database query (cache is in-memory)
- Device changes take effect on next recording cycle (~2-3 seconds)

## Example Usage

### List Available Devices

```bash
curl http://localhost:8123/audio/devices \
  -H "X-API-Key: dev-change-me"
```

### Switch to USB Microphone

```bash
curl -X PUT http://localhost:8123/audio/device \
  -H "Content-Type: application/json" \
  -H "X-API-Key: dev-change-me" \
  -d '{"device_index": 1}'
```

### Check Current Device in Logs

```
[INFO] Audio device changed: 0 -> 1
```

## Troubleshooting

### No Audio Devices Found

**Symptoms:**
```
[WARNING] No audio input devices found!
```

**Solutions:**
- Check if microphone is connected and enabled
- Verify sounddevice can access audio devices
- Run: `python -c "import sounddevice; print(sounddevice.query_devices())"`

### Invalid Device Index

**Symptoms:**
```json
{
  "detail": "Invalid device index 5. Available: [0, 1, 2]"
}
```

**Solutions:**
- Call `GET /audio/devices` to see available indices
- Update request with valid index
- Check startup logs for device enumeration

### Device Not Working

**Symptoms:**
- No audio captured
- Silence in transcriptions

**Solutions:**
- Verify device is not muted or disabled in OS settings
- Check sample rate compatibility (16kHz recommended)
- Try selecting a different device via API
- Review worker logs for recording errors

## Future Enhancements

- [ ] Hot-plug detection (detect when devices are added/removed)
- [ ] Per-device sample rate configuration
- [ ] Audio level monitoring endpoint
- [ ] Device capability testing (test recording from each device)
- [ ] Automatic fallback on device failure
