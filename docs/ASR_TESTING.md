# ASR Worker Testing Guide

## Test Mode

The ASR worker supports a **test mode** that uses pre-recorded audio files instead of a live microphone. This allows you to:

- ✅ Test wake word detection with known audio samples
- ✅ Test the worker stays alive and processes files continuously  
- ✅ Test trigger → active mode transitions
- ✅ Test session management and timeout behavior
- ✅ Run reproducible tests without microphone hardware
- ✅ Simulate various speech scenarios

## Setup

### 1. Create Test Audio Directory

```bash
mkdir -p test_audio/trigger test_audio/active
```

### 2. Add Test Audio Files

Place WAV files in the appropriate directories:

**`test_audio/trigger/`** - Files with wake words:
- `hey_astraea.wav` - Recording saying "Hey Astraea, what's the weather?"
- `hello_echobell.wav` - Recording saying "Hello EchoBell, tell me a joke"
- `no_wake_word.wav` - Recording without wake word (should be ignored)

**`test_audio/active/`** - Files for active mode testing:
- `question.wav` - Recording of a follow-up question
- `answer.wav` - Recording of a response
- `conversation.wav` - Longer conversational audio

**`test_audio/silence.wav`** (optional) - Silent audio for timeout testing

### 3. Enable Test Mode

In your `.env` file:

```bash
ECHONET_TEST_MODE=true
ECHONET_TEST_AUDIO_DIR=test_audio
ECHONET_TEST_LOOP_DELAY=3.0  # Wait 3 seconds between cycles
```

### 4. Start Echonet

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8123
```

## How It Works

### Audio Streaming Simulation

**Test mode streams audio files in small chunks** (100ms by default) to accurately simulate microphone input:

- 📦 File is read in 100ms chunks (1600 samples at 16kHz)
- ⏱️ Each chunk has a 100ms delay (real-time simulation)
- 🔊 Chunks are concatenated before transcription
- ✅ This matches the behavior of actual microphone input

This is crucial for testing because:
- Real microphones stream audio continuously
- Energy-based VAD operates on small chunks
- Whisper VAD requires streaming data
- Buffer management behaves realistically

### Test Mode Flow

```
Start ASR Worker
      ↓
   Test Mode Detected
      ↓
   Read Mode (trigger/active)
      ↓
   ┌─────────────────┐
   │ mode=trigger?   │
   └────┬────────────┘
        │
   ┌────┴─────────────────┐
   │                      │
   ▼ YES                  ▼ NO (active)
Load trigger/*.wav    Load active/*.wav
   │                      │
   ▼                      ▼
For each file:
   1. Stream audio in 100ms chunks
   2. Concatenate chunks
   3. Transcribe with Whisper
   4. Check wake word (trigger) or route all (active)
   5. Send to routing logic
   6. Log results with chunk count
   │
   ▼
Wait test_loop_delay
   │
   ▼
Repeat cycle
```

### Logs You'll See

```
[INFO] ASR worker starting...
[INFO] 🧪 TEST MODE ENABLED - Using pre-recorded audio files
[INFO]    Test audio directory: test_audio
[INFO] Streaming audio file: test_audio/trigger/hey_astraea.wav (16000Hz, 1ch)
[INFO] Found 3 trigger test files, 2 active test files
[INFO] 🧪 Test cycle #1 - Mode: trigger
[INFO] 📁 Processing: hey_astraea.wav
[INFO]    Received 35 chunks (3.50s of audio)
[INFO]    Transcribed in 0.45s: 'hey astraea what's the weather' (confidence: 0.89)
[INFO]    ✅ Wake word detected: 'hey astraea' -> target astraea
[INFO]    Routed to: astraea (mode: session_open)
```
[INFO] 📁 Processing: no_wake_word.wav
[INFO]    Transcribed in 0.38s: 'this is just random speech' (confidence: 0.92)
[INFO]    ❌ No wake word detected
[INFO] 🧪 Test cycle #1 complete, waiting 3.0s
[INFO] 🧪 Test cycle #2 - Mode: trigger
...
```

## Creating Test Audio

### Option 1: Record Your Own

```bash
# Windows (PowerShell)
# Use Voice Recorder app and save as WAV

# Linux
arecord -f cd -d 3 test_audio/trigger/hey_astraea.wav

# macOS
# Use QuickTime Player → File → New Audio Recording
```

### Option 2: Generate with Python

```python
import numpy as np
import soundfile as sf

# Create a simple test file with silence
sample_rate = 16000
duration = 2.0
silence = np.zeros(int(sample_rate * duration), dtype=np.float32)
sf.write('test_audio/silence.wav', silence, sample_rate)

# Create a tone (for testing non-speech audio)
t = np.linspace(0, duration, int(sample_rate * duration))
tone = 0.3 * np.sin(2 * np.pi * 440 * t)  # 440Hz
sf.write('test_audio/tone.wav', tone.astype(np.float32), sample_rate)
```

### Option 3: Text-to-Speech

Use TTS to generate wake word samples:

```python
# Using pyttsx3
import pyttsx3
import wave

engine = pyttsx3.init()
engine.save_to_file('Hey Astraea, what is the weather?', 'test_audio/trigger/hey_astraea.wav')
engine.runAndWait()
```

## Testing Scenarios

### Scenario 1: Wake Word Detection

**Goal**: Verify worker detects wake words and routes correctly

**Setup**:
1. Create `trigger/hey_astraea.wav` with wake word
2. Create `trigger/no_wake_word.wav` without wake word
3. Set `ECHONET_TEST_MODE=true`
4. Ensure state is in trigger mode

**Expected Behavior**:
- `hey_astraea.wav` → Wake word detected → Routes to astraea
- `no_wake_word.wav` → No wake word → Ignored

### Scenario 2: Mode Switching

**Goal**: Test trigger → active → trigger transitions

**Setup**:
1. Create trigger and active test files
2. Start in trigger mode
3. Manually switch modes via API

**Steps**:
```bash
# Worker starts in trigger mode, processes trigger/*.wav files
# Watch logs for wake word detection

# Switch to active mode
curl -X PUT http://localhost:8123/state \
  -H "Content-Type: application/json" \
  -H "X-API-Key: dev-change-me" \
  -d '{"target":"astraea","source":"test","state":"active","reason":"Testing"}'

# Worker switches to active mode, processes active/*.wav files
# Watch logs - all text should be routed

# Switch back to trigger
curl -X PUT http://localhost:8123/state \
  -H "Content-Type: application/json" \
  -H "X-API-Key: dev-change-me" \
  -d '{"target":"astraea","source":"test","state":"trigger","reason":"Testing"}'
```

**Expected Behavior**:
- Mode changes reflected in logs
- Different files processed based on mode
- Routing behavior changes (wake word check vs. route all)

### Scenario 3: Worker Persistence

**Goal**: Verify worker stays alive and processes continuously

**Setup**:
1. Add multiple test files
2. Set `ECHONET_TEST_LOOP_DELAY=5.0` (5 second cycles)
3. Start worker

**Expected Behavior**:
- Worker processes all files in cycle #1
- Waits 5 seconds
- Starts cycle #2 and processes all files again
- Continues indefinitely until stopped
- No crashes or hangs

### Scenario 4: Transcription Accuracy

**Goal**: Test Whisper transcription quality

**Setup**:
1. Create audio files with known text
2. Compare transcription output to expected text

**Example**:
```python
# Create test file with known phrase
expected_text = "hey astraea what is the weather today"
# Record or generate audio saying this phrase
# Check logs for transcription:
# [INFO]    Transcribed: 'hey astraea what's the weather today'
# Compare and validate accuracy
```

## Test Mode vs. Production

| Feature | Test Mode | Production Mode |
|---------|-----------|-----------------|
| Audio Source | Pre-recorded files | Live microphone |
| Timing | Fixed loop delay | Real-time streaming |
| Repeatability | ✅ 100% reproducible | ❌ Varies by input |
| VAD | ❌ Not used (full file loaded) | ✅ Stops on silence |
| Device Selection | N/A | ✅ Configurable |
| Debugging | ✅ Easy to isolate issues | ❌ Harder to reproduce |
| CI/CD | ✅ Perfect for automation | ❌ Requires hardware |

## Troubleshooting

### No Test Files Found

```
[WARNING] No test audio files found!
```

**Solution**: Create `test_audio/trigger/` and `test_audio/active/` directories with WAV files.

### Failed to Load Audio

```
[WARNING] Failed to load or empty audio: test.wav
```

**Solutions**:
- Check file is valid WAV format
- Install soundfile: `pip install soundfile`
- Try converting: `ffmpeg -i input.mp3 -ar 16000 -ac 1 output.wav`

### Worker Not Processing Files

**Check**:
- Test mode enabled: `ECHONET_TEST_MODE=true`
- Test directory path correct
- Files are `.wav` format
- Check logs for errors

### Transcription Empty

```
[INFO]    Empty transcription, skipping routing
```

**Possible Causes**:
- Audio file is silent/too quiet
- Audio quality too poor for Whisper
- File corrupted

**Solutions**:
- Check audio plays correctly in media player
- Increase volume of recording
- Re-record with better quality microphone

## Example Directory Structure

```
echonet/
├── test_audio/
│   ├── trigger/
│   │   ├── hey_astraea_weather.wav
│   │   ├── hey_astraea_joke.wav
│   │   ├── hello_echobell.wav
│   │   └── no_wake_word.wav
│   ├── active/
│   │   ├── question_1.wav
│   │   ├── answer_1.wav
│   │   ├── question_2.wav
│   │   └── conversation.wav
│   └── silence.wav
├── .env (ECHONET_TEST_MODE=true)
└── app/
```

## Automated Testing Script

```bash
#!/bin/bash
# test_asr_worker.sh

echo "Starting ASR worker test..."

# Enable test mode
export ECHONET_TEST_MODE=true
export ECHONET_TEST_AUDIO_DIR=test_audio
export ECHONET_TEST_LOOP_DELAY=2.0

# Start server in background
uvicorn app.main:app --host 0.0.0.0 --port 8123 &
SERVER_PID=$!

# Wait for startup
sleep 5

# Monitor logs for specific patterns
echo "Monitoring worker behavior..."
tail -f logs/echonet.log | grep -E "🧪|Wake word|Routed to" &
TAIL_PID=$!

# Let it run for 30 seconds (should complete ~15 cycles with 2s delay)
sleep 30

# Check if worker is still alive
if ps -p $SERVER_PID > /dev/null; then
   echo "✅ Worker stayed alive for 30 seconds"
else
   echo "❌ Worker crashed"
fi

# Cleanup
kill $TAIL_PID $SERVER_PID
echo "Test complete"
```

## Summary

Test mode allows you to:
- ✅ Test ASR worker without microphone hardware
- ✅ Verify wake word detection works
- ✅ Test mode switching (trigger ↔ active)
- ✅ Ensure worker stays alive continuously
- ✅ Debug transcription and routing issues
- ✅ Run reproducible automated tests
- ✅ Validate before deploying to production

Perfect for development, testing, and CI/CD pipelines!
