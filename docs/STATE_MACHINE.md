# State Machine Reference

This document provides a comprehensive reference for EchoNet's three-mode state machine.

## Quick Reference

| Mode | Recording | Transcription | Wake Word Check | Routes Audio | Auto-Reset |
|------|-----------|---------------|-----------------|--------------|------------|
| **Inactive** | ❌ No | ❌ No | ❌ No | ❌ No | ❌ No |
| **Trigger** | ✅ Yes | ✅ Yes | ✅ Yes | Only if wake word found | ❌ No |
| **Active** | ✅ Yes | ✅ Yes | ❌ No | ✅ All transcriptions | ✅ Yes (→ Trigger) |

## State Diagram

```
                    ┌──────────────────────────────────────┐
                    │                                      │
                    │         EchoNet State Machine        │
                    │                                      │
                    └──────────────────────────────────────┘

    ╔══════════════╗              ╔══════════════╗              ╔══════════════╗
    ║              ║              ║              ║              ║              ║
    ║   INACTIVE   ║◄────────────►║   TRIGGER    ║◄────────────►║    ACTIVE    ║
    ║              ║   API only   ║              ║   API only   ║              ║
    ║  (not rec)   ║              ║ (wake word)  ║              ║ (continuous) ║
    ╚══════════════╝              ╚══════════════╝              ╚══════════════╝
         │                             │     ▲                        │
         │                             │     │                        │
         │ No transitions              │     │                        │
         │ (stays until API)           │     │                        │
         │                             │     └────────────────────────┘
         │                             │        Auto-reset after
         │                             │        recording completes
         │                             │
         └─────────────────────────────┘
           All transitions via API
           (bi-directional)
```

## Mode Descriptions

### Inactive Mode

**Purpose**: Complete shutdown of recording for privacy or power management.

**Behavior**:
- ❌ Microphone not accessed
- ❌ No audio recording
- ❌ No transcription processing
- ❌ No CPU usage for ASR
- ❌ No network traffic for routing
- Worker loop just sleeps (0.5s intervals)

**Entry Conditions**:
- API call: `PUT /state` with `state="inactive"`
- Can transition from: Trigger or Active

**Exit Conditions**:
- API call: `PUT /state` with `state="trigger"` or `state="active"`
- No automatic exit (stays inactive until API command)

**Use Cases**:
- Physical mute button pressed
- Scheduled privacy hours (e.g., 10 PM - 7 AM)
- Battery low (power saving mode)
- Testing non-audio functionality
- Device leaving room (laptop closing lid)

**Related Documentation**:
- [ADR 002: Inactive Mode](./adr/002-inactive-mode.md)

---

### Trigger Mode (Default)

**Purpose**: Listen for wake words while preserving privacy.

**Behavior**:
- ✅ Records audio continuously in sessions (until VAD detects silence)
- ✅ Transcribes all recorded audio
- ✅ Checks transcription against registered wake word phrases
- ✅ Routes to targets ONLY if wake word detected
- ❌ Discards audio/transcriptions without wake words

**Entry Conditions**:
- System startup (default mode)
- API call: `PUT /state` with `state="trigger"`
- Auto-reset from Active mode after recording completes
- Can transition from: Inactive or Active

**Exit Conditions**:
- API call: `PUT /state` with `state="inactive"` or `state="active"`
- Typically stays in trigger mode most of the time

**Use Cases**:
- Default listening state
- "Hey Alexa" / "OK Google" style interaction
- Waiting for user to initiate interaction
- Privacy-conscious continuous monitoring

**Privacy Note**: Records and transcribes ALL audio, but only forwards transcriptions containing registered wake words. Audio without wake words is discarded.

---

### Active Mode

**Purpose**: Continuous listening during active conversation or interaction.

**Behavior**:
- ✅ Records audio continuously in sessions (until VAD detects silence)
- ✅ Transcribes all recorded audio
- ❌ Does NOT check for wake words
- ✅ Routes ALL non-empty transcriptions to targets
- ✅ **Auto-resets to Trigger mode** after recording completes

**Entry Conditions**:
- API call: `PUT /state` with `state="active"`
- Typically requested by targets after wake word detected
- Can transition from: Inactive or Trigger

**Exit Conditions**:
- **Automatic**: After recording session completes (VAD detects silence)
- **Manual**: API call: `PUT /state` with `state="inactive"` or `state="trigger"`

**Use Cases**:
- LLM asked a question, waiting for user's answer
- Doorbell button pressed, waiting for command
- Follow-up questions without repeating wake word
- Active conversation flow

**Auto-Reset Rationale**: Prevents system from staying in "route all audio" mode indefinitely. After each recording session, automatically returns to Trigger mode for privacy/efficiency. See [ADR 001](./adr/001-automatic-active-mode-reset.md).

---

## Transition Matrix

| From → To | Inactive | Trigger | Active |
|-----------|----------|---------|--------|
| **Inactive** | - | API | API |
| **Trigger** | API | - | API |
| **Active** | API | API or Auto-Reset | - |

**Legend**:
- `API` = Transition via `PUT /state` endpoint
- `Auto-Reset` = Automatic transition after recording completes
- `-` = Same state (no transition)

## API Reference

### Change Mode

**Endpoint**: `PUT /state`

**Headers**:
```
Content-Type: application/json
X-API-Key: <your-api-key>
```

**Body**:
```json
{
  "target": "target_id",
  "source": "source_id",
  "state": "inactive|trigger|active",
  "reason": "Human-readable explanation"
}
```

**Examples**:

#### Mute (Inactive)
```bash
curl -X PUT http://localhost:8123/state \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-key" \
  -d '{
    "target": "system",
    "source": "mute_button",
    "state": "inactive",
    "reason": "User pressed mute"
  }'
```

#### Unmute (Trigger)
```bash
curl -X PUT http://localhost:8123/state \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-key" \
  -d '{
    "target": "system",
    "source": "mute_button",
    "state": "trigger",
    "reason": "User pressed unmute"
  }'
```

#### Start Conversation (Active)
```bash
curl -X PUT http://localhost:8123/state \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-key" \
  -d '{
    "target": "llm_assistant",
    "source": "wake_word_detected",
    "state": "active",
    "reason": "User said wake word, starting conversation"
  }'
```

### Query Current Mode

**Endpoint**: `GET /state`

**Response**:
```json
{
  "listen_mode": "trigger",
  "updated_at": "2025-01-09T10:30:00Z"
}
```

## Database Tracking

All mode changes are logged in the `settings_log` table for audit purposes:

| Column | Type | Description |
|--------|------|-------------|
| `id` | INTEGER | Primary key |
| `setting_name` | TEXT | Always `"listen_mode"` for mode changes |
| `value` | TEXT | Mode: `"inactive"`, `"trigger"`, or `"active"` |
| `target` | TEXT | Target identifier from API request |
| `source` | TEXT | Source identifier from API request |
| `reason` | TEXT | Human-readable reason for change |
| `created_at` | TIMESTAMP | When the change occurred |

**Query Example**:
```sql
SELECT * FROM settings_log 
WHERE setting_name = 'listen_mode' 
ORDER BY created_at DESC 
LIMIT 10;
```

This shows the last 10 mode changes with full context.

## Testing

### Unit Tests

**File**: `tests/test_inactive_mode.py`

Tests for inactive mode state management:
- `test_inactive_mode_state`: Verifies inactive mode can be set and retrieved
- `test_invalid_mode_raises_error`: Validates only valid modes accepted
- `test_mode_transitions`: Tests all valid transitions

**File**: `tests/test_integration_modes.py`

Integration tests for mode transitions and ASR behavior:
- `test_trigger_mode_with_wake_word`: Wake word detection in trigger mode
- `test_trigger_mode_without_wake_word`: Audio discarded without wake word
- `test_active_mode_routes_all`: All audio routed in active mode
- `test_mode_transition`: State changes via API

### Run Tests

```bash
# All tests
pytest

# Mode-specific tests
pytest tests/test_inactive_mode.py
pytest tests/test_integration_modes.py

# With coverage
pytest --cov=app --cov-report=html
```

## Troubleshooting

### Mode Not Changing

**Problem**: API call succeeds but mode doesn't change.

**Check**:
1. Verify API response: `curl http://localhost:8123/state`
2. Check database: `sqlite3 data/echonet.db "SELECT * FROM settings;"`
3. Check logs for errors: `docker logs echonet`
4. Restart ASR worker: `docker restart echonet`

**Common Cause**: Cache not updating. Fixed in current implementation.

---

### Stuck in Active Mode

**Problem**: Mode stays in active even after conversation ends.

**Expected Behavior**: Active mode should auto-reset to trigger after recording completes.

**Check**:
1. Verify auto-reset is happening: Check logs for "Resetting to trigger mode"
2. If not resetting, this is a bug (report it)
3. Manual workaround: Call API to set mode to trigger

---

### Recording When Inactive

**Problem**: System still recording in inactive mode.

**Expected Behavior**: Inactive mode should NOT access microphone.

**Check**:
1. Verify current mode: `curl http://localhost:8123/state`
2. Check logs: Should show "Inactive mode - not recording"
3. If recording in inactive mode, this is a bug (report it)

---

## Related Documentation

- [ASR Worker Architecture](./ASR_WORKER.md) - Detailed ASR implementation
- [ADR 001: Automatic Active Mode Reset](./adr/001-automatic-active-mode-reset.md)
- [ADR 002: Inactive Mode](./adr/002-inactive-mode.md)
- [API Documentation](./API.md) - Complete API reference

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2025-01-09 | Initial documentation of three-mode system |
