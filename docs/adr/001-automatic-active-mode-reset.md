# ADR 001: Automatic Reset from Active to Trigger Mode

**Status:** Accepted  
**Date:** 2026-01-21  
**Decision Makers:** System Architecture  
**Context:** ASR worker mode management  

---

## Context

EchoNet operates in two distinct listening modes:

1. **Trigger Mode** - Waits for wake words (e.g., "Peter") before routing transcriptions
2. **Active Mode** - Routes all transcriptions without wake word filtering

External systems (targets) can switch EchoNet to active mode via the `/state/listen_mode` API endpoint. This enables conversational interaction after detecting user intent.

**Problem:** What should happen after active mode completes a recording session? Should it:
- Stay in active mode (requiring explicit reset)
- Automatically reset to trigger mode
- Use a timeout-based approach

---

## Decision

**Active mode will automatically reset to trigger mode** after completing any recording session.

The reset occurs in three scenarios:
1. **Successful recording** - Audio captured, transcribed, and routed
2. **Empty transcription** - Audio captured but transcription was empty
3. **Timeout with no audio** - `record_until_silence()` returned None

Reset is performed by calling:
```python
state_manager.set_listen_mode(
    mode="trigger",
    source="asr_worker",
    reason="Active mode recording completed"
)
```

---

## Rationale

### Why Auto-Reset?

**1. Predictable State Lifecycle**
- Active mode is event-driven (triggered by external intent detection)
- Natural lifecycle: Trigger → Active (external) → Trigger (automatic)
- Prevents getting "stuck" in active mode if external system fails to reset

**2. Safety & Resource Management**
- Active mode routes ALL audio (no filtering)
- Prevents unintended continuous routing if external reset fails
- Returns to secure default state (wake word filtering)

**3. Simplifies Integration**
- External systems don't need to track mode state
- One-way interaction: "switch to active" → system handles the rest
- Reduces integration complexity and failure modes

**4. Clear Audit Trail**
- Every mode transition logged in `settings_log`
- `source="asr_worker"` clearly identifies automatic resets
- Debugging and monitoring easier with explicit state changes

### Why Not Stay in Active Mode?

**Risks of staying active:**
- ❌ Continuous routing of all audio (privacy/performance concern)
- ❌ Requires external system to explicitly reset (failure mode)
- ❌ Complex state synchronization between systems
- ❌ No clear timeout/recovery mechanism

### Why Not Timeout-Based?

**Considered but rejected:**
- ⚠️ Arbitrary timeout values hard to tune
- ⚠️ Doesn't align with natural conversation boundaries
- ⚠️ VAD already provides silence detection (natural boundary)

---

## Alternatives Considered

### Alternative 1: Manual Reset Only
External systems explicitly call API to reset to trigger mode.

**Rejected because:**
- Adds complexity to every integration
- Creates failure mode if reset call fails
- No graceful degradation

### Alternative 2: Multi-Recording Active Sessions
Stay in active mode for multiple recordings until explicit reset.

**Rejected because:**
- Unclear session boundaries
- Security risk (continuous routing)
- Doesn't match conversational UX patterns

### Alternative 3: Configurable Behavior
Make auto-reset optional via configuration.

**Rejected because:**
- Adds unnecessary complexity
- Two behavior modes harder to test/maintain
- Current approach works for all known use cases

---

## Consequences

### Positive

✅ **Predictable behavior** - Always returns to safe default state  
✅ **Simplified integration** - External systems send one command  
✅ **Better security** - Minimizes time in "route all audio" mode  
✅ **Clear audit trail** - All transitions logged with source/reason  
✅ **Natural flow** - Aligns with silence detection boundaries  

### Negative

⚠️ **Multi-turn conversations** - Requires re-triggering active mode for each turn  
⚠️ **Extra API calls** - External systems must re-trigger for follow-up questions  

### Mitigation

For multi-turn conversations, external systems can:
1. Detect continued user intent in response
2. Immediately re-trigger active mode before next recording
3. Use wake word detection as conversation restart signal

---

## Implementation

### Code Changes

**File:** `app/asr_worker.py`  
**Function:** `_handle_active_mode()`

```python
async def _handle_active_mode(
    state_manager: StateManager,
    device_index: int,
    stop_event: asyncio.Event
) -> None:
    """
    Active mode: Continuous recording and transcription.
    Records until silence is detected (person stops talking).
    
    After completing a recording (or timing out with no audio), automatically
    resets back to trigger mode via the state manager.
    """
    # Record until silence
    audio = await record_until_silence(...)
    
    # Handle timeout (no audio)
    if not has_audio:
        log.info("Active mode: No audio captured, resetting to trigger mode")
        state_manager.set_listen_mode(
            mode="trigger",
            source="asr_worker",
            reason="Active mode timeout with no audio"
        )
        return
    
    # Transcribe and route
    text, confidence = await transcribe_audio(audio)
    if text.strip() and _text_handler:
        await _text_handler(text_input)
        log.info("Active mode: Recording processed successfully, resetting to trigger mode")
    else:
        log.info("Active mode: Empty transcription, resetting to trigger mode")
    
    # Reset to trigger mode after any outcome
    state_manager.set_listen_mode(
        mode="trigger",
        source="asr_worker",
        reason="Active mode recording completed"
    )
```

### Testing

**Integration Tests:** `tests/test_integration_modes.py`

1. `test_active_mode_routes_all_text` - Verifies mode reset after successful routing
2. `test_active_mode_resets_on_timeout` - Verifies mode reset on timeout

Both tests verify:
- Text routing behavior
- Final mode state is "trigger"
- Audit log entries created

---

## Monitoring & Observability

### Key Metrics

1. **Mode transition frequency** - Track `settings_log` entries with `source="asr_worker"`
2. **Active mode duration** - Time between external trigger and auto-reset
3. **Timeout rate** - Percentage of active mode sessions ending in timeout

### Log Messages

```
INFO: Active mode: Recording processed successfully, resetting to trigger mode
INFO: Active mode: Empty transcription, resetting to trigger mode
INFO: Active mode: No audio captured, resetting to trigger mode
```

### Database Audit

All transitions recorded in `settings_log` table:
```sql
SELECT * FROM settings_log 
WHERE name = 'listen_mode' 
  AND source = 'asr_worker'
ORDER BY changed_at DESC;
```

---

## References

- **Related Docs:** `docs/ASR_WORKER.md` - ASR worker architecture
- **Related ADR:** (None - first ADR)
- **API Spec:** `/state/listen_mode` endpoint in `app/main.py`
- **State Management:** `STATE_MANAGEMENT.md`

---

## Review & Updates

**Next Review:** 2026-03-01 (after production deployment)

**Update Criteria:**
- If multi-turn conversation requirements change
- If timeout behavior needs tuning
- If new mode types are added

**Change Log:**
- 2026-01-21: Initial decision and implementation
