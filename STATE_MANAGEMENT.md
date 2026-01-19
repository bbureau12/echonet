# State Management in Echonet

## Overview

Echonet includes a robust state management system to track application state, particularly the **listen mode** which determines whether the system is:

- **🎯 Trigger Mode** (idle): Listening passively for activation phrases
- **🎙️ Active Mode**: Actively listening for user responses to LLM questions

All state changes are automatically logged with full audit trail including timestamp, source, and reason.

## Database Schema

### `settings` Table
Stores current state values:
```sql
CREATE TABLE settings (
    name TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    description TEXT
);
```

### `settings_log` Table
Audit trail of all state changes:
```sql
CREATE TABLE settings_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    old_value TEXT,
    new_value TEXT NOT NULL,
    changed_at TEXT NOT NULL DEFAULT (datetime('now')),
    source TEXT,
    reason TEXT
);
```

## Listen Mode States

### Trigger Mode (Default)
- System is **idly listening** for activation phrases
- When a phrase is detected, it routes to the appropriate target
- Most of the time, the system should be in this mode

### Active Mode
- System is **actively listening** for responses
- Used when an LLM has asked a question and is waiting for user response
- Should automatically return to trigger mode after response or timeout

## API Usage

### Get Current State
```bash
GET /state
```

**Response:**
```json
{
  "ok": true,
  "settings": [
    {
      "name": "listen_mode",
      "value": "trigger",
      "updated_at": "2026-01-19 12:00:00",
      "description": "Current listening mode: trigger (idle) or active (responding to LLM)"
    }
  ],
  "listen_mode": "trigger"
}
```

### Get State Change History
```bash
GET /state/history?name=listen_mode&limit=50
```

**Query Parameters:**
- `name` (optional): Filter by setting name
- `limit` (optional): Number of records to return (max 500, default 50)

**Response:**
```json
{
  "ok": true,
  "count": 3,
  "changes": [
    {
      "id": 3,
      "name": "listen_mode",
      "old_value": "active",
      "new_value": "trigger",
      "changed_at": "2026-01-19 12:05:00",
      "source": "session_timeout",
      "reason": "No response received within timeout"
    },
    {
      "id": 2,
      "name": "listen_mode",
      "old_value": "trigger",
      "new_value": "active",
      "changed_at": "2026-01-19 12:00:00",
      "source": "llm_question",
      "reason": "Astraea asked: What would you like to do?"
    }
  ]
}
```

### Set Listen Mode
```bash
PUT /state
Content-Type: application/json
```

**Request Body:**
```json
{
  "target": "astraea",
  "source": "llm",
  "state": "active",
  "reason": "Asked: What would you like to do?"
}
```

**Fields:**
- `target` (required): Name of the registered target triggering the state change
- `source` (required): Source of the change (e.g., "llm", "timeout", "user", "api")
- `state` (required): Either "trigger" or "active"
- `reason` (optional): Description of why the state changed

**Validation:**
- Target must be registered (returns 404 if not found)
- State must be either "trigger" or "active" (returns 400 for invalid values)
- Requires admin key if `ECHONET_ADMIN_KEY` is configured

**Response:**
```json
{
  "ok": true,
  "listen_mode": "active",
  "target": "astraea",
  "source": "llm",
  "message": "Listen mode set to 'active' by target 'astraea'"
}
```

**Error Responses:**
```json
// Target not found
{
  "ok": false,
  "error": "Target 'unknown' not found. Register the target first."
}

// Invalid state
{
  "ok": false,
  "error": "Invalid listen_mode: invalid. Must be 'trigger' or 'active'"
}
```

## Python API

### Basic Usage

```python
from app.state import StateManager

# Initialize
state = StateManager(db_path="echonet_registry.db")

# Get current listen mode
mode = state.get_listen_mode()  # Returns "trigger" or "active"

# Check mode with convenience methods
if state.is_trigger_mode():
    print("Listening for activation phrases...")

if state.is_active_mode():
    print("Actively listening for response...")

# Set listen mode
state.set_listen_mode(
    mode="active",
    source="llm_question",
    reason="Astraea asked a question"
)

# Later, return to trigger mode
state.set_listen_mode(
    mode="trigger",
    source="response_received",
    reason="User answered the question"
)
```

### Custom Settings

```python
# Set any custom state
state.set(
    name="custom_flag",
    value="true",
    source="api",
    reason="User enabled feature",
    description="Custom feature flag"
)

# Get setting value
value = state.get_value("custom_flag", default="false")

# Get full setting object
setting = state.get("custom_flag")
print(f"{setting.name} = {setting.value} (updated: {setting.updated_at})")

# Get all settings
all_settings = state.all()
for s in all_settings:
    print(f"{s.name}: {s.value}")
```

### View Change History

```python
# Get history for specific setting
changes = state.get_history(name="listen_mode", limit=10)
for change in changes:
    print(f"{change.changed_at}: {change.old_value} → {change.new_value}")
    print(f"  Source: {change.source}, Reason: {change.reason}")

# Get all history
all_changes = state.get_history(limit=100)
```

## Command-Line Tools

### View Current State
```powershell
python inspect_state.py
```

**Output:**
```
📊 Echonet Application State: echonet_registry.db
======================================================================

🔹 LISTEN_MODE
   Value: trigger
   Updated: 2026-01-19 13:55:58
   Description: Current listening mode: trigger (idle) or active (responding to LLM)

======================================================================
Total Settings: 1

🎯 Current Listen Mode: TRIGGER
```

### View Change History
```powershell
# All changes
python inspect_state.py --history

# Filter by setting
python inspect_state.py --history --setting listen_mode

# More entries
python inspect_state.py --history --limit 100
```

## Workflow Examples

### Example 1: LLM Asks a Question

**Via API:**
```bash
# Astraea (LLM) asks a question, sets to active mode
curl -X PUT http://localhost:8123/state \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key" \
  -H "X-Admin-Key: your-admin-key" \
  -d '{
    "target": "astraea",
    "source": "llm",
    "state": "active",
    "reason": "Asked: What color would you like?"
  }'

# User responds...

# Return to trigger mode
curl -X PUT http://localhost:8123/state \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key" \
  -H "X-Admin-Key: your-admin-key" \
  -d '{
    "target": "astraea",
    "source": "llm",
    "state": "trigger",
    "reason": "Received answer: blue"
  }'
```

**Via Python:**
```python
# LLM (e.g., Astraea) is about to ask a question
state.set_listen_mode(
    mode="active",
    source="llm:astraea",
    reason="Asking: What color would you like?"
)

# System now actively listens for response...
# User responds...

# Return to idle listening
state.set_listen_mode(
    mode="trigger",
    source="llm:astraea",
    reason="Received answer: blue"
)
```

### Example 2: Timeout Handling

```python
# LLM asked a question
state.set_listen_mode(mode="active", source="llm", reason="Question asked")

# Wait for response with timeout...
# If timeout occurs:
if timeout_occurred:
    state.set_listen_mode(
        mode="trigger",
        source="timeout",
        reason="No response within 30 seconds"
    )
```

### Example 3: Manual Override via API

```bash
# Switch to active mode manually
curl -X PUT http://localhost:8123/state \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key" \
  -H "X-Admin-Key: your-admin-key" \
  -d '{
    "target": "astraea",
    "source": "admin",
    "state": "active",
    "reason": "Manual testing"
  }'

# Check current state
curl http://localhost:8123/state \
  -H "X-API-Key: your-api-key"

# View recent changes
curl "http://localhost:8123/state/history?limit=10" \
  -H "X-API-Key: your-api-key"
```

## Best Practices

1. **Always Log Source and Reason**: When changing state, provide meaningful source and reason for debugging
   ```python
   state.set_listen_mode("active", source="astraea", reason="Asked about weather")
   ```

2. **Use Convenience Methods**: For listen_mode, use the dedicated methods
   ```python
   # Good
   state.set_listen_mode("active")
   
   # Also works but less convenient
   state.set("listen_mode", "active")
   ```

3. **Check Mode Before Actions**: Verify state before taking actions
   ```python
   if state.is_trigger_mode():
       # Listen for activation phrases
   elif state.is_active_mode():
       # Process user response to LLM
   ```

4. **Review History for Debugging**: Use the audit trail to understand mode transitions
   ```python
   changes = state.get_history(name="listen_mode", limit=20)
   for c in changes:
       print(f"{c.changed_at}: {c.reason}")
   ```

5. **Handle Errors Gracefully**: Invalid modes raise ValueError
   ```python
   try:
       state.set_listen_mode("invalid_mode")
   except ValueError as e:
       log.error(f"Invalid mode: {e}")
   ```

## Migration from In-Memory State

If you previously tracked state in memory (e.g., a global variable), the migration is simple:

**Before:**
```python
# Global variable
current_mode = "trigger"

# Change mode
current_mode = "active"

# Check mode
if current_mode == "trigger":
    # ...
```

**After:**
```python
# Initialize once
state = StateManager()

# Change mode (with logging!)
state.set_listen_mode("active", source="llm", reason="Question asked")

# Check mode
if state.is_trigger_mode():
    # ...
```

Benefits:
- ✅ Persistent across restarts
- ✅ Full audit trail
- ✅ API access to state
- ✅ Debugging via change history
- ✅ Thread-safe database operations

## Future Extensions

The state system is designed to be extensible. You can add new state variables:

```python
# Track conversation count
state.set("conversation_count", "42", description="Total conversations today")

# Track last active target
state.set("last_target", "astraea", source="routing", reason="Last activation")

# Feature flags
state.set("experimental_mode", "true", description="Enable experimental features")
```

All will automatically get change tracking and persistence!
