# ADR 002: Add Inactive Mode for Privacy and Power Management

**Status:** Accepted  
**Date:** 2026-01-23  
**Decision Makers:** System Architecture  
**Context:** ASR worker mode management, privacy controls  

---

## Context

EchoNet originally had two listening modes:

1. **Trigger Mode** - Continuously records, transcribes, and checks for wake words
2. **Active Mode** - Continuously records, transcribes, and routes all audio

**Problem:** There was no way to completely stop recording for:
- Privacy (user wants recording explicitly disabled)
- Power management (reduce CPU/battery usage when not needed)
- Compliance (regulatory requirements to disable recording)
- Testing/debugging (isolate non-audio functionality)

Users had no "off switch" - the system was always listening and recording.

---

## Decision

Add a third mode: **`inactive`** - completely stops all audio recording.

The system now has three states:
1. **`inactive`** - Not recording (microphone not accessed)
2. **`trigger`** - Recording with wake word filtering
3. **`active`** - Recording without filtering (routes all audio)

### State Transitions

```
inactive ←→ trigger ←→ active
   ↑                      ↓
   └──────────────────────┘
```

All transitions are bi-directional via API calls.

### Implementation

**ASR Worker Behavior:**
```python
if mode == "inactive":
    # Do nothing, just sleep
    await asyncio.sleep(0.5)
elif mode == "trigger":
    # Record and check for wake words
    await _handle_trigger_mode(...)
elif mode == "active":
    # Record and route all audio
    await _handle_active_mode(...)
```

---

## Rationale

### Why Add Inactive Mode?

**1. Privacy Control**
- Users need explicit "not recording" state
- Clear distinction between "listening for wake words" and "completely off"
- Meets privacy expectations ("mute" button should really mute)

**2. Resource Management**
- Continuous recording uses CPU for VAD/transcription
- Raspberry Pi deployments benefit from power savings
- Network traffic reduced (no transcriptions sent)

**3. System Design**
- Clean separation of concerns (inactive = truly off)
- Simplifies debugging (can test routing without audio)
- Enables graceful degradation (disable ASR if microphone fails)

**4. User Experience**
- Physical mute button → inactive mode
- Leave-the-house scenario → disable recording
- Privacy mode during sensitive conversations

### Why Not Just Stop the ASR Worker?

**Rejected alternatives:**
- Stopping the worker thread requires restart
- Loses state and configuration
- Slower to resume than mode switch
- More complex lifecycle management

---

## Alternatives Considered

### Alternative 1: Just Use Trigger Mode as "Off"
Users could unregister all targets so no wake words exist.

**Rejected because:**
- Still recording and transcribing (wasteful)
- Unclear to users that it's "off"
- No way to distinguish "no targets" from "disabled"

### Alternative 2: Pause/Resume Methods
Add `pause()` and `resume()` methods to ASR worker.

**Rejected because:**
- Adds new API surface (modes are sufficient)
- Doesn't fit the state-based architecture
- Mode switching already exists

### Alternative 3: Binary On/Off State
Replace trigger/active with simple on/off.

**Rejected because:**
- Loses important distinction between trigger and active
- Would require complete redesign
- Current two-mode system works well for conversational UX

---

## Consequences

### Positive

✅ **Explicit privacy control** - Users can completely disable recording  
✅ **Power savings** - No CPU used for VAD/transcription in inactive mode  
✅ **Clear state model** - Three distinct, well-defined states  
✅ **Backward compatible** - Existing trigger/active modes unchanged  
✅ **Graceful degradation** - System can run without audio subsystem  
✅ **Testing flexibility** - Can test routing without audio recording  

### Negative

⚠️ **More complex state machine** - Three states instead of two  
⚠️ **Documentation updates** - Need to explain three modes vs two  
⚠️ **API changes** - StateUpdate model now accepts three values  

### Neutral

◽ **Default remains "trigger"** - No behavior change for existing deployments  
◽ **Transitions unrestricted** - Can go directly from inactive to active if needed  

---

## Implementation

### Code Changes

**1. State Manager** (`app/state.py`)
```python
def set_listen_mode(self, mode: str, source: Optional[str] = None, reason: Optional[str] = None):
    """Set listen mode to 'inactive', 'trigger', or 'active'."""
    if mode not in ("inactive", "trigger", "active"):
        raise ValueError(f"Invalid listen_mode: {mode}")
    self.set("listen_mode", mode, source=source, reason=reason)

def is_inactive_mode(self) -> bool:
    """Check if currently in inactive (not recording) mode."""
    return self.get_listen_mode() == "inactive"
```

**2. ASR Worker** (`app/asr_worker.py`)
```python
if mode == "inactive":
    # Inactive mode: do nothing, just sleep
    await asyncio.sleep(0.5)
elif mode == "trigger":
    # Trigger mode: listen for wake words
    await _handle_trigger_mode(...)
elif mode == "active":
    # Active mode: continuous recording
    await _handle_active_mode(...)
```

**3. API Model** (`app/models.py`)
```python
class StateUpdate(BaseModel):
    state: Literal["inactive", "trigger", "active"] = Field(...)
```

**4. Settings** (`app/settings.py`)
```python
initial_listen_mode: str = "trigger"  # "inactive", "trigger", or "active"
```

### Migration

No database migration needed - `listen_mode` is stored as string in `settings` table.

### Testing

**New tests:** `tests/test_inactive_mode.py`
- `test_inactive_mode_state()` - Verify inactive mode can be set/retrieved
- `test_invalid_mode_raises_error()` - Verify invalid modes rejected
- `test_mode_transitions()` - Verify all state transitions work

All existing tests pass without modification.

---

## Use Cases

### Use Case 1: Privacy Button
Physical hardware button sets mode to inactive:
```http
POST /state/listen_mode
{
  "state": "inactive",
  "target": "system",
  "source": "hardware_button",
  "reason": "User pressed mute button"
}
```

### Use Case 2: Power Saving
Mobile deployment goes inactive when not in use:
```http
POST /state/listen_mode
{
  "state": "inactive",
  "target": "system",
  "source": "power_manager",
  "reason": "Battery below 20%"
}
```

### Use Case 3: Scheduled Privacy
Disable recording during specific hours:
```http
POST /state/listen_mode
{
  "state": "inactive",
  "target": "system",
  "source": "scheduler",
  "reason": "Quiet hours (10 PM - 7 AM)"
}
```

---

## Related Decisions

- **[ADR 001](./001-automatic-active-mode-reset.md)** - Active mode auto-reset (inactive not affected)

---

## Future Considerations

### Potential Enhancements

1. **Visual indicator API** - Query mode for LED/UI display
2. **Mode history** - Track time spent in each mode (analytics)
3. **Automatic transitions** - Schedule-based mode switching
4. **Hardware integration** - GPIO pin for physical mute button

### Questions for Later

- Should inactive mode persist across restarts?
- Should there be a timeout to auto-return from inactive?
- Do we need sub-states (e.g., "inactive_temporary" vs "inactive_permanent")?

**Current decision:** Keep it simple. Inactive is inactive until changed via API.

---

## Monitoring & Observability

### Key Metrics

1. **Time in inactive mode** - Percentage of uptime not recording
2. **Mode transition frequency** - How often users toggle modes
3. **Inactive reasons** - Why users disable recording (privacy, power, schedule)

### Log Messages

```
INFO: Mode changed: trigger -> inactive
INFO: Mode changed: inactive -> trigger
```

### Database Queries

All mode changes logged in `settings_log`:
```sql
SELECT * FROM settings_log 
WHERE name = 'listen_mode' 
  AND new_value = 'inactive'
ORDER BY changed_at DESC;
```

---

## Documentation Updates

**Files updated:**
- ✅ `app/state.py` - Docstrings updated
- ✅ `app/asr_worker.py` - Comments added for inactive handling
- ✅ `app/models.py` - API documentation updated
- ✅ `tests/test_inactive_mode.py` - Test documentation

**Files needing update:**
- 📝 API documentation (add inactive mode examples)
- 📝 User guide (explain three modes)
- 📝 Deployment guide (hardware mute button integration)

---

## Review & Updates

**Next Review:** 2026-03-01 (after production deployment)

**Update Criteria:**
- If users request sub-states or variants of inactive
- If power savings metrics show need for optimization
- If privacy regulations require additional controls

**Change Log:**
- 2026-01-23: Initial decision and implementation
