# Echonet

Echonet is a lightweight **text event router + session manager** for the EchoBell ecosystem.

- **Inputs:** text events (`POST /text`) from future listener nodes (mics/phones), or from Postman.
- **Targets:** "brains" like **EchoBell** and **Astraea** (registered via `POST /register`).
- **Sessions:** per-source open-listen mode (wake phrase → route subsequent text to that target until timeout/cancel).

Echonet does **not** do ASR, and does **not** speak. Targets decide output and may call Bellphonics.

## Features

✅ **Persistent Registry**: Target registrations are stored in SQLite and survive restarts  
✅ **State Tracking**: Listen mode (trigger vs active) tracked with full audit history  
✅ **mDNS Discovery**: Automatic service discovery on local network (zone/subzone aware)  
✅ **ASR Integration**: Designed for Automatic Speech Recognition workflows  
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

Echonet tracks application state to distinguish between:
- **🎯 Trigger Mode** (idle): Listening for activation phrases
- **🎙️ Active Mode**: Actively listening for responses to LLM questions

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

See [MIGRATION_SQLITE.md](MIGRATION_SQLITE.md) for detailed documentation.
