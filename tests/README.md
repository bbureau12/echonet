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
│   └── awake_word/           # Wake word test audio files
│       └── *.wav             # Recordings with "Peter" wake word
└── test_wake_word_regression.py
```

## Wake Word Regression Tests

### Test Audio Files

Place WAV files in `tests/fixtures/awake_word/` with the following content:

**Example recording:**
- "Peter, I would like a cup of coffee" 
- [~5 seconds of silence]
- "Also I would like a slice of cake"

### Test Coverage

The wake word tests verify:

1. **Wake word detection** - "Peter" is correctly identified
2. **Phrase extraction** - Text after wake word is captured
3. **Session boundaries** - 5-second silence gap prevents second phrase
4. **Routing logic** - Wake word maps to correct target
5. **Streaming behavior** - Audio chunks are correctly processed

### Expected Results

✅ First phrase should be transcribed (contains "peter" and "coffee")  
✅ Wake word "peter" should be detected  
✅ Should route to "peter_target"  
❌ Second phrase should NOT be included (no "cake" or "slice")  
❌ Second phrase should NOT route (no wake word)

## Creating Test Audio

You can create test audio files using:

1. **Audacity** - Record, add silence gaps, export as WAV
2. **Python** - Use soundfile/scipy to create synthetic audio
3. **Online TTS** - Generate speech with pauses

### Recommended format:
- **Format:** WAV (PCM)
- **Sample rate:** 16000 Hz
- **Channels:** Mono
- **Bit depth:** 16-bit

## Troubleshooting

### Import errors
Make sure Echonet is installed in development mode:
```powershell
pip install -e .
```

### Audio file not found
Check that your WAV file is in `tests/fixtures/awake_word/`:
```powershell
ls tests/fixtures/awake_word/
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
