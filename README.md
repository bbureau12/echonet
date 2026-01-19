# Echonet

Echonet is a lightweight **text event router + session manager** for the EchoBell ecosystem.

- **Inputs:** text events (`POST /text`) from future listener nodes (mics/phones), or from Postman.
- **Targets:** "brains" like **EchoBell** and **Astraea** (registered via `POST /register`).
- **Sessions:** per-source open-listen mode (wake phrase → route subsequent text to that target until timeout/cancel).

Echonet does **not** do ASR, and does **not** speak. Targets decide output and may call Bellphonics.

## Features

✅ **Persistent Registry**: Target registrations are stored in SQLite and survive restarts  
✅ **ASR Integration**: Designed for Automatic Speech Recognition workflows  
✅ **Activation Phrases**: Each target has customizable wake phrases  
✅ **Session Management**: Maintains conversation context per source  
✅ **API Key Security**: Protected endpoints with API keys  

## Quickstart

```powershell
python -m venv .venv
.\.venv\Scripts\activate
pip install -e .
copy .env.example .env
uvicorn app.main:app --host 0.0.0.0 --port 8123
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

# Inspect registered targets
python inspect_registry.py

# Backup database to JSON
python backup_registry.py backup

# Restore from backup
python backup_registry.py restore registry_backup_20260119_120000.json
```

See [MIGRATION_SQLITE.md](MIGRATION_SQLITE.md) for detailed documentation.
