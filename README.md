# Echonet

Echonet is a lightweight **microphone listener + text event router + session manager** for the EchoBell ecosystem.

- **Inputs:** 
  - **🎤 Microphone**: Built-in ASR with Faster Whisper (automatic speech recognition)
  - **📡 API**: Text events (`POST /text`) from other services or manual testing
- **Targets:** "brains" like **EchoBell** and **Astraea** (registered via `POST /register`).
- **Sessions:** per-source open-listen mode (wake phrase → route subsequent text to that target until timeout/cancel).
- **Modes:**
  - **Inactive Mode**: Not recording (privacy/power saving)
  - **Trigger Mode**: Listen for wake words, only route when detected
  - **Active Mode**: Route all audio (during LLM conversations), auto-resets

## Features

✅ **Built-in Microphone ASR**: Faster Whisper speech-to-text with voice activity detection  
✅ **Three Recording Modes**: Inactive (muted), Trigger (wake word), Active (continuous)  
✅ **Auto-Reset Privacy**: Active mode automatically returns to trigger after recording  
✅ **Voice Activity Detection**: Stops recording when you stop talking (Whisper VAD + energy)  
✅ **Multi-Device Support**: Enumerate and select audio input devices at runtime  
✅ **Persistent Registry**: Target registrations stored in SQLite, survive restarts  
✅ **State Tracking**: Listen mode tracked with full audit history  
✅ **mDNS Discovery**: Automatic service discovery on local network (zone/subzone aware)  
✅ **Activation Phrases**: Each target has customizable wake phrases  
✅ **Session Management**: Maintains conversation context per source  
✅ **API Key Security**: Protected endpoints with API keys and allowlist  

## Quickstart

```powershell
python -m venv .venv
.\.venv\Scripts\activate
pip install -e .
copy .env.example .env
uvicorn app.main:app --host 0.0.0.0 --port 8123
```

## Microphone & ASR Setup

Echonet includes a built-in ASR worker that listens to your microphone and transcribes speech using Faster Whisper.

### Audio Device Configuration

On startup, Echonet will enumerate all available audio input devices:

```
[INFO] Found 3 audio input devices:
[INFO]   [0] Microphone (Realtek High Definition Audio) (DEFAULT)
[INFO]   [1] USB Microphone (Blue Yeti)
[INFO]   [2] Line In (Realtek High Definition Audio)
[INFO] Using system default audio device: Microphone (index 0)
```

**Environment Configuration:**
```bash
# Audio device settings
ECHONET_AUDIO_DEVICE_INDEX=0  # 0 = first device or system default
ECHONET_AUDIO_SAMPLE_RATE=16000  # 16kHz optimal for speech
ECHONET_AUDIO_CHANNELS=1  # 1=mono, 2=stereo

# Voice Activity Detection (VAD)
ECHONET_AUDIO_SILENCE_DURATION=1.0  # Stop after 1s of silence
ECHONET_AUDIO_MIN_DURATION=0.5  # Minimum recording length
ECHONET_AUDIO_MAX_DURATION=30.0  # Maximum recording length (safety)
ECHONET_AUDIO_ENERGY_THRESHOLD=0.01  # Energy threshold for sound detection
ECHONET_AUDIO_USE_WHISPER_VAD=true  # Use AI speech detection (vs. energy-only)

# Faster Whisper model settings
ECHONET_WHISPER_MODEL=base  # tiny, base, small, medium, large-v2, large-v3
ECHONET_WHISPER_DEVICE=cpu  # cpu or cuda
ECHONET_WHISPER_COMPUTE_TYPE=int8  # int8 (cpu) or float16 (gpu)
ECHONET_WHISPER_LANGUAGE=en  # language code or "auto"
```

**Runtime Device Selection:**
```bash
# List available devices
curl http://localhost:8123/audio/devices -H "X-API-Key: your-key"

# Switch to different device
curl -X PUT http://localhost:8123/audio/device \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-key" \
  -d '{"device_index": 1}'
```

### How Voice Activity Detection Works

Echonet uses a **hybrid two-stage approach** for accurate speech detection:

1. **Energy Check (Fast)**: Quick volume analysis to filter out obvious silence
2. **Whisper VAD (Accurate)**: AI-based speech detection to distinguish speech from noise

This means recording stops when you **actually stop talking**, not just when the room gets quiet. Background music, door slams, and other non-speech sounds are ignored.

**Recording Flow:**
- Start recording when sound/speech detected
- Keep recording while you're talking
- Stop automatically after 1 second of silence (configurable)
- Maximum 30 second timeout for safety

### Operating Modes

**🎯 Trigger Mode** (default):
- Listens for wake words only
- Records audio, transcribes with Whisper
- Checks if any registered wake phrase is detected
- Only forwards to target if wake word found
- Max 10 second recording (wake words are brief)

**🎙️ Active Mode** (during conversations):
- Continuous transcription of all speech
- Records until you stop talking
- Sends all transcriptions to active session target
- Max 30 second recording (conversations can be longer)
- Automatically set by LLM responses

**Mode switching** happens automatically via the state API (see State Management below).


## Discovery & Configuration

Echonet advertises itself via mDNS (if enabled) so LLMs and other services can discover it automatically.

**Check service info:**
```bash
curl http://localhost:8123/handshake -H "X-API-Key: your-key"
```

**Response includes:**
- Discovery info (zone, subzone, host, port)
- Capabilities (ASR, routing, sessions, state tracking)
- Configuration (timeouts, cancel phrases)

**Environment Variables:**
```bash
ECHONET_DISCOVERY_ENABLED=true
ECHONET_DISCOVERY_NAME="Echonet Main Floor"
ECHONET_DISCOVERY_ZONE=home
ECHONET_DISCOVERY_SUBZONE=main-floor
```

## Database & Persistence

Target registrations are persisted to SQLite (`echonet_registry.db` by default).

**Migrations**: The database schema is managed through an automatic migration system that runs on startup. Schema changes are tracked and applied automatically.

**Configuration**: Set database path via environment variable:
```env
ECHONET_DB_PATH=./data/registry.db
```

**Management Tools**:
```powershell
# Check migration status
python migrate_db.py --status

# View current state (listen mode, etc.)
python inspect_state.py

# View state change history
python inspect_state.py --history

# Inspect registered targets
python inspect_registry.py

# Backup database to JSON
python backup_registry.py backup

# Restore from backup
python backup_registry.py restore registry_backup_20260119_120000.json
```

## State Management

Echonet tracks application state to distinguish between operating modes:
- **🎯 Trigger Mode** (idle): Listening for activation phrases only
- **🎙️ Active Mode**: Actively listening for responses to LLM questions

The ASR worker automatically adapts its behavior based on the current mode.

**API Endpoints**:
```bash
# Get current state
GET /state

# Get state change history  
GET /state/history?name=listen_mode&limit=50

# Set listen mode (requires admin key)
PUT /state
Content-Type: application/json
{
  "target": "astraea",
  "source": "llm",
  "state": "active",
  "reason": "Asked question"
}
```

All state changes are automatically logged with timestamp, source, and reason for full audit trail.

## Example Workflow

### 1. Register a Target

```bash
curl -X POST http://localhost:8123/register \
  -H "Content-Type: application/json" \
  -H "X-API-Key: dev-change-me" \
  -d '{
    "name": "astraea",
    "base_url": "http://astraea.local:9001",
    "phrases": ["hey astraea", "astraea"]
  }'
```

### 2. Say the Wake Word

With the microphone running in **trigger mode**:
- You say: *"Hey Astraea, what's the weather?"*
- Echonet transcribes and detects "hey astraea"
- Opens a session with Astraea
- Forwards the text to `http://astraea.local:9001/listen`

### 3. LLM Switches to Active Mode

When Astraea (the LLM) asks a question, it calls:

```bash
curl -X PUT http://localhost:8123/state \
  -H "Content-Type: application/json" \
  -H "X-API-Key: dev-change-me" \
  -d '{
    "target": "astraea",
    "source": "llm_response",
    "state": "active",
    "reason": "Asked user a question"
  }'
```

Now Echonet is in **active mode** - continuously transcribing all speech and forwarding to Astraea.

### 4. Conversation Continues

- You say: *"It's sunny"*
- Echonet transcribes and sends to Astraea (no wake word needed)
- Session continues until timeout or cancel phrase

### 5. Return to Trigger Mode

After the conversation ends:

```bash
curl -X PUT http://localhost:8123/state \
  -H "Content-Type: application/json" \
  -H "X-API-Key: dev-change-me" \
  -d '{
    "target": "astraea",
    "source": "conversation_end",
    "state": "trigger",
    "reason": "Conversation complete"
  }'
```

Back to listening for wake words only.

## Documentation

- **[ASR Worker Architecture](docs/ASR_WORKER.md)**: Detailed explanation of trigger/active modes and state management
- **[Audio Device Management](docs/AUDIO_DEVICES.md)**: Device enumeration, selection, and configuration
- **[Migration Guide](MIGRATION_SQLITE.md)**: SQLite database schema and migrations

See [MIGRATION_SQLITE.md](MIGRATION_SQLITE.md) for detailed documentation.