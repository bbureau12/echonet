# Testing Echonet Without a Microphone

For development and CI/CD testing, Echonet provides test endpoints that allow you to validate the transcription and routing pipeline without requiring physical microphone hardware.

## Why Test Endpoints?

- **Reproducible Tests**: Use the same audio files repeatedly
- **CI/CD Integration**: Run automated tests in headless environments
- **No Hardware Required**: Test on servers, containers, or systems without audio devices
- **Faster Development**: Skip microphone setup during development
- **Debugging**: Isolate issues in transcription vs routing

## Test Endpoints

### 1. Upload Audio File for Transcription

**Endpoint**: `POST /test/transcribe`

Upload a pre-recorded audio file to test the Faster Whisper transcription pipeline.

**Supported Formats**:
- WAV (PCM)
- MP3
- FLAC
- OGG
- Any format supported by `soundfile`

**Parameters**:
- `file` (required): Audio file to transcribe
- `process_text` (optional, query param): If `true`, also route the transcribed text through the normal routing flow

#### Example: Transcription Only

```bash
curl -X POST http://localhost:8123/test/transcribe \
  -H "X-API-Key: dev-change-me" \
  -F "file=@test_audio.wav"
```

**Response**:
```json
{
  "text": "hey astraea what's the weather",
  "confidence": 0.89,
  "duration": 2.3,
  "processing_time": 0.45,
  "route_decision": null
}
```

#### Example: Transcription + Routing

Test the complete pipeline (transcription → wake word detection → target routing):

```bash
curl -X POST "http://localhost:8123/test/transcribe?process_text=true" \
  -H "X-API-Key: dev-change-me" \
  -F "file=@wake_word_test.wav"
```

**Response**:
```json
{
  "text": "hey astraea tell me a joke",
  "confidence": 0.92,
  "duration": 1.8,
  "processing_time": 0.38,
  "route_decision": {
    "handled": true,
    "routed_to": "astraea",
    "mode": "session_open",
    "session": {
      "id": "...",
      "target": "astraea",
      "source_id": "test_upload",
      "room": "default",
      "last_ts": 1234567890,
      "expires_in_s": 25
    },
    "forwarded": true,
    "reason": "trigger_phrase:hey astraea"
  }
}
```

### 2. Simulate Speech with Text

**Endpoint**: `POST /test/simulate-speech`

Bypass audio/transcription entirely and test just the routing logic. Useful for testing wake word detection, session management, and target forwarding without any audio processing.

**Request Body**: `TextIn` object (same as `POST /text`)

```json
{
  "source_id": "test_mic",
  "room": "living-room",
  "ts": 1234567890,
  "text": "hey astraea, what is the weather?",
  "confidence": 0.95
}
```

#### Example: Test Wake Word Detection

```bash
curl -X POST http://localhost:8123/test/simulate-speech \
  -H "Content-Type: application/json" \
  -H "X-API-Key: dev-change-me" \
  -d '{
    "source_id": "test_mic",
    "room": "living-room",
    "ts": 1234567890,
    "text": "hey astraea, what is the weather?",
    "confidence": 0.95
  }'
```

**Response**:
```json
{
  "handled": true,
  "routed_to": "astraea",
  "mode": "session_open",
  "session": {
    "id": "test_mic_1234567890",
    "target": "astraea",
    "source_id": "test_mic",
    "room": "living-room",
    "last_ts": 1234567890,
    "expires_in_s": 25
  },
  "forwarded": true,
  "reason": "trigger_phrase:hey astraea"
}
```

#### Example: Test Session Continuation

Once a session is open, subsequent text is routed to the same target:

```bash
# First message opens session
curl -X POST http://localhost:8123/test/simulate-speech \
  -H "Content-Type: application/json" \
  -H "X-API-Key: dev-change-me" \
  -d '{"source_id": "test_mic", "ts": 100, "text": "hey astraea tell me a joke", "confidence": 0.9}'

# Second message continues session (no wake word needed)
curl -X POST http://localhost:8123/test/simulate-speech \
  -H "Content-Type: application/json" \
  -H "X-API-Key: dev-change-me" \
  -d '{"source_id": "test_mic", "ts": 110, "text": "actually make it about cats", "confidence": 0.85}'
```

The second request will show `"mode": "session_continue"` since the session is already open.

#### Example: Test Cancel Phrase

```bash
curl -X POST http://localhost:8123/test/simulate-speech \
  -H "Content-Type: application/json" \
  -H "X-API-Key: dev-change-me" \
  -d '{"source_id": "test_mic", "ts": 120, "text": "never mind", "confidence": 0.95}'
```

Response will show `"mode": "session_end"` and `"reason": "cancel_phrase"`.

## Creating Test Audio Files

### Using Python

```python
import numpy as np
import soundfile as sf

# Generate 2 seconds of silence
sample_rate = 16000
duration = 2.0
audio = np.zeros(int(sample_rate * duration), dtype=np.float32)

# Save as WAV
sf.write('test_silence.wav', audio, sample_rate)

# Or add a sine wave (simulated sound)
t = np.linspace(0, duration, int(sample_rate * duration))
audio = 0.3 * np.sin(2 * np.pi * 440 * t)  # 440Hz tone
sf.write('test_tone.wav', audio.astype(np.float32), sample_rate)
```

### Record Your Own

Use any audio recording software to create test files:
- **Windows**: Voice Recorder
- **macOS**: QuickTime Player
- **Linux**: `arecord -f cd -d 5 test.wav`
- **Python**: `sounddevice` library

Save as 16kHz mono WAV for best results (though other formats work too).

## Automated Testing

### pytest Example

```python
import pytest
import httpx
from pathlib import Path

BASE_URL = "http://localhost:8123"
API_KEY = "dev-change-me"
HEADERS = {"X-API-Key": API_KEY}

@pytest.mark.asyncio
async def test_transcribe_audio():
    """Test audio file transcription."""
    async with httpx.AsyncClient() as client:
        with open("tests/fixtures/test_audio.wav", "rb") as f:
            files = {"file": ("test.wav", f, "audio/wav")}
            response = await client.post(
                f"{BASE_URL}/test/transcribe",
                headers=HEADERS,
                files=files
            )
    
    assert response.status_code == 200
    data = response.json()
    assert "text" in data
    assert "confidence" in data
    assert data["duration"] > 0

@pytest.mark.asyncio
async def test_wake_word_detection():
    """Test wake word triggers session."""
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{BASE_URL}/test/simulate-speech",
            headers=HEADERS,
            json={
                "source_id": "test",
                "ts": 1000,
                "text": "hey astraea what's up",
                "confidence": 0.9
            }
        )
    
    assert response.status_code == 200
    data = response.json()
    assert data["handled"] is True
    assert data["routed_to"] == "astraea"
    assert data["mode"] == "session_open"

@pytest.mark.asyncio
async def test_session_continuation():
    """Test session continues without wake word."""
    async with httpx.AsyncClient() as client:
        # Open session
        await client.post(
            f"{BASE_URL}/test/simulate-speech",
            headers=HEADERS,
            json={"source_id": "test", "ts": 1000, "text": "hey astraea", "confidence": 0.9}
        )
        
        # Continue session
        response = await client.post(
            f"{BASE_URL}/test/simulate-speech",
            headers=HEADERS,
            json={"source_id": "test", "ts": 1005, "text": "tell me more", "confidence": 0.9}
        )
    
    data = response.json()
    assert data["mode"] == "session_continue"
```

## Use Cases

### 1. Development
Test routing logic without setting up microphone hardware.

### 2. CI/CD Pipeline
```yaml
# .github/workflows/test.yml
- name: Test Transcription Pipeline
  run: |
    uvicorn app.main:app &
    sleep 5
    curl -X POST http://localhost:8123/test/simulate-speech \
      -H "Content-Type: application/json" \
      -H "X-API-Key: dev-change-me" \
      -d '{"source_id":"ci","ts":1,"text":"hey astraea test","confidence":0.9}' \
      | jq '.handled'
```

### 3. Performance Testing
Measure transcription speed with various audio files:

```bash
for file in test_audio/*.wav; do
  curl -X POST http://localhost:8123/test/transcribe \
    -H "X-API-Key: dev-change-me" \
    -F "file=@$file" \
    | jq '.processing_time'
done
```

### 4. Model Comparison
Test different Whisper models by changing config and uploading same audio.

### 5. Wake Word Testing
Create audio samples for each wake phrase and verify detection:

```bash
# Test all wake words
for phrase in "hey_astraea" "hey_echobell"; do
  curl -X POST "http://localhost:8123/test/transcribe?process_text=true" \
    -H "X-API-Key: dev-change-me" \
    -F "file=@samples/${phrase}.wav" \
    | jq '.route_decision.routed_to'
done
```

## Differences from Production

### Test Endpoints
- ✅ Use same transcription engine (Faster Whisper)
- ✅ Use same routing logic
- ✅ Use same session management
- ❌ Don't use Voice Activity Detection (fixed duration)
- ❌ Source ID is "test_upload" not from microphone
- ❌ No real-time streaming

### Production Microphone
- ✅ Real-time VAD (stops on silence)
- ✅ Configurable audio device
- ✅ Dual mode (trigger/active)
- ✅ Continuous operation
- ❌ Requires hardware
- ❌ Not reproducible

## Troubleshooting

### "Import soundfile could not be resolved"

Install dependencies:
```bash
pip install soundfile python-multipart
```

### "Unsupported audio format"

Convert to WAV with ffmpeg:
```bash
ffmpeg -i input.mp3 -ar 16000 -ac 1 output.wav
```

### "Text handler not set"

Ensure server started completely before testing. Check logs for:
```
[INFO] Set up text handler for ASR worker
```

## Summary

Test endpoints allow you to:
- ✅ Test Whisper transcription with pre-recorded audio
- ✅ Test wake word detection and routing
- ✅ Test session management
- ✅ Run automated tests without microphone
- ✅ Develop and debug faster
- ✅ Create reproducible test cases

This makes Echonet much easier to develop, test, and deploy!
