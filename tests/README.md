# Echonet Test Suite

## Setup

Install test dependencies:

```powershell
pip install -e ".[dev]"
```

Or manually:
```powershell
pip install pytest pytest-asyncio
```

## Running Tests

### Run all tests:
```powershell
pytest
```

### Run specific test file:
```powershell
pytest tests/test_wake_word_regression.py
```

### Run specific test:
```powershell
pytest tests/test_wake_word_regression.py::TestWakeWordDetection::test_peter_coffee_phrase
```

### Run with verbose output:
```powershell
pytest -v
```

### Run with output capture disabled (see print statements):
```powershell
pytest -s
```

## Test Structure

```
tests/
├── __init__.py
├── fixtures/
│   ├── __init__.py
│   ├── awake_word/           # Wake word test audio files
│   │   └── *.wav             # Recordings with "Peter" wake word
│   └── active_mode/          # Active mode test audio files
│       └── *.wav             # Recordings without wake word requirement
├── test_wake_word_regression.py    # Component tests for wake word detection
├── test_active_mode_regression.py  # Component tests for active mode recording
└── test_integration_modes.py       # Integration tests for mode handlers
```

## Test Coverage Overview

### Component Tests (Unit/Regression)
These tests verify individual components work correctly in isolation:
- ✅ **VAD (Voice Activity Detection)**: Stops at silence gaps correctly
- ✅ **Transcription**: Converts audio to text accurately  
- ✅ **Wake word detection**: Identifies specific phrases in transcribed text
- ✅ **Routing logic**: Maps wake words to correct targets

### Integration Tests
These tests verify components work together correctly in the actual mode handlers:
- ✅ **Trigger mode flow**: VAD → Transcription → Registry lookup → Routing decision
- ✅ **Active mode flow**: VAD → Transcription → Routing (no wake word check)

## Test Files Explained

### test_wake_word_regression.py
**Type**: Component/Regression tests  
**Purpose**: Verify wake word detection components work correctly

**What it tests:**
- ✅ VAD stops at silence gaps using chunked streaming (simulates production)
- ✅ Transcription produces correct text from audio
- ✅ Wake word "peter" is present in transcribed text
- ✅ Routing logic maps wake words to correct targets

**What it does NOT test:**
- ❌ Actual `_handle_trigger_mode()` function call
- ❌ End-to-end flow through trigger mode handler

**Test approach:**
1. Streams WAV file in chunks (0.5s) to simulate real-time audio
2. Applies Whisper VAD to detect silence and stop recording
3. Transcribes captured audio
4. Manually checks if wake word appears in text
5. Verifies routing mappings separately

**Example test:**
```python
def test_realistic_vad_simulation():
    """Simulates production VAD with chunked streaming"""
    # 1. Stream audio chunks (like microphone input)
    audio = await simulate_record_until_silence_from_file(...)
    
    # 2. Transcribe captured audio
    result = transcribe_audio(audio, ...)
    
    # 3. Manually check for wake word
    assert "peter" in result.text.lower()
    assert "coffee" in result.text.lower()
    assert "cake" not in result.text.lower()  # Stopped at silence
```

### test_active_mode_regression.py
**Type**: Component/Regression tests  
**Purpose**: Verify active mode recording works correctly

**What it tests:**
- ✅ VAD captures audio and stops at silence gaps
- ✅ Transcription works in active mode
- ✅ No wake word filtering (all text is captured)

**What it does NOT test:**
- ❌ Actual `_handle_active_mode()` function call
- ❌ End-to-end flow through active mode handler

**Test approach:**
1. Streams WAV file in chunks (same as trigger mode)
2. Applies VAD to detect silence
3. Transcribes captured audio
4. Verifies expected phrase is present (no wake word check)

**Example test:**
```python
def test_realistic_active_mode_vad():
    """Simulates active mode recording with VAD"""
    # 1. Stream audio chunks
    audio = await simulate_record_until_silence_from_file(...)
    
    # 2. Transcribe
    result = transcribe_audio(audio, ...)
    
    # 3. Check for expected phrase (no wake word required)
    assert "hold on tight" in result.text.lower()
    assert "dangerous" not in result.text.lower()  # Stopped at silence
```

### test_integration_modes.py
**Type**: Integration tests  
**Purpose**: Verify complete mode handler flows

**What it tests:**
- ✅ Actual `_handle_trigger_mode()` function with all dependencies
- ✅ Actual `_handle_active_mode()` function with all dependencies
- ✅ Registry lookup and routing decision logic
- ✅ Text handler is called correctly based on mode

**Test approach:**
1. Mocks `record_until_silence` to return pre-recorded audio
2. Calls actual mode handler function (`_handle_trigger_mode()` or `_handle_active_mode()`)
3. Verifies text handler is called (or not called) correctly
4. Checks routing decision matches expected behavior

**Example tests:**
```python
async def test_trigger_mode_with_wake_word_routes():
    """INTEGRATION: Trigger mode should route when wake word detected"""
    # Mock recording to return pre-recorded audio
    monkeypatch.setattr(audio_io, 'record_until_silence', mock_record)
    
    # Call actual trigger mode handler
    await _handle_trigger_mode(
        state_manager=state,
        registry=registry,
        device_index=0,
        stop_event=stop_event
    )
    
    # Verify text handler was called
    assert mock_text_handler.called
    assert "peter" in mock_text_handler.call_args[0][0].text.lower()

async def test_trigger_mode_without_wake_word_ignores():
    """INTEGRATION: Trigger mode should NOT route without wake word"""
    # Mock recording to return audio without wake word
    monkeypatch.setattr(audio_io, 'record_until_silence', mock_record)
    
    # Call actual trigger mode handler
    await _handle_trigger_mode(...)
    
    # Verify text handler was NOT called
    assert not mock_text_handler.called

async def test_active_mode_routes_all_text():
    """INTEGRATION: Active mode should route ALL text (no wake word check)"""
    # Mock recording to return any audio
    monkeypatch.setattr(audio_io, 'record_until_silence', mock_record)
    
    # Call actual active mode handler
    await _handle_active_mode(...)
    
    # Verify text handler was called (no wake word required)
    assert mock_text_handler.called
```

## Test Audio Files

### Wake Word Test Files (fixtures/awake_word/)

Place WAV files with the following structure:

**Example recording:**
- "Peter, I would like a cup of coffee" 
- [~1+ second of silence]
- "Also I would like a slice of cake"

**Expected behavior:**
- ✅ First phrase captured (contains "peter" and "coffee")
- ✅ Recording stops at silence gap
- ❌ Second phrase NOT captured (no "cake")

### Active Mode Test Files (fixtures/active_mode/)

Place WAV files with any speech content:

**Example recording:**
- "Hold on tight, this is going to be dangerous"
- [~1+ second of silence]
- "We need to make ends meet"

**Expected behavior:**
- ✅ First phrase captured ("hold on tight", "dangerous")
- ✅ Recording stops at silence gap
- ❌ Second phrase NOT captured (no "make ends meet")

### Creating Test Audio

You can create test audio files using:

1. **Audacity** - Record, add silence gaps, export as WAV
2. **Python** - Use soundfile/scipy to create synthetic audio
3. **Online TTS** - Generate speech with pauses

**Recommended format:**
- **Format:** WAV (PCM)
- **Sample rate:** 16000 Hz
- **Channels:** Mono
- **Bit depth:** 16-bit

## Key Testing Concepts

### Why Both Component and Integration Tests?

**Component tests** verify each piece works correctly:
- VAD detects silence correctly
- Transcription is accurate
- Wake word detection logic works
- Faster to run, easier to debug

**Integration tests** verify pieces work together:
- Mode handlers call components in correct order
- Registry lookup happens correctly
- Routing decision is made properly
- Catches integration bugs (API mismatches, state issues)

### Simulating Production Behavior

Both test types use `simulate_record_until_silence_from_file()` which:
1. Streams audio in 0.5s chunks (like real microphone)
2. Applies Whisper VAD to each chunk
3. Detects silence gaps (>1s)
4. Stops recording (like production code)

This ensures tests match actual runtime behavior, not just "load WAV and transcribe".

## Troubleshooting

### Import errors
Make sure Echonet is installed in development mode:
```powershell
pip install -e .
```

### Audio file not found
Check that your WAV file is in the correct fixtures directory:
```powershell
ls tests/fixtures/awake_word/
ls tests/fixtures/active_mode/
```

### Transcription failing
Ensure Whisper model is downloaded (happens on first run):
```powershell
python -c "from faster_whisper import WhisperModel; WhisperModel('base')"
```

### Async test errors
Install pytest-asyncio:
```powershell
pip install pytest-asyncio
```

### Integration tests fail but component tests pass
This usually means:
- API mismatch between components
- State management issue
- Registry configuration problem
Check the integration test output for specific error messages.
