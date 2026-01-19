# SQLite Registry Migration Guide

## Overview

The Echonet target registry has been migrated from an in-memory dictionary to a SQLite database for persistence across restarts. This ensures that registered doorbell AI listeners and their activation phrases are not lost when the service restarts.

## What Changed

### Before (In-Memory)
- Targets were stored in a Python dictionary (`dict[str, Target]`)
- All registrations were lost on restart
- No persistence between service restarts

### After (SQLite)
- Targets are stored in a SQLite database (`echonet_registry.db`)
- Registrations persist across restarts
- Thread-safe database operations with proper connection management

## Database Schema

```sql
CREATE TABLE targets (
    name TEXT PRIMARY KEY,
    base_url TEXT NOT NULL,
    phrases TEXT NOT NULL  -- JSON array
);

CREATE INDEX idx_target_name ON targets(name COLLATE NOCASE);
```

## Configuration

You can configure the database path via environment variable:

```bash
ECHONET_DB_PATH=./data/registry.db
```

Or in your `.env` file:

```env
ECHONET_DB_PATH=./data/registry.db
```

Default: `echonet_registry.db` (in the working directory)

## Database Migrations

The database schema is managed through a migration system that runs automatically on application startup. This ensures:
- ✅ Schema is always up-to-date
- ✅ Future schema changes are applied automatically
- ✅ Migration history is tracked

### Migration Scripts

**Check migration status:**
```powershell
python migrate_db.py --status
```

**Run migrations manually:**
```powershell
python migrate_db.py --migrate
```

Migrations are normally run automatically when the application starts, but the manual script is useful for:
- Troubleshooting database issues
- Pre-creating the database before first run
- Verifying migration state

### Current Schema Version: v1

**v1 - Initial Schema**
- `schema_version` table - tracks migration history
- `targets` table - stores target registrations
- Case-insensitive name index

## API Changes

### New Endpoint

**DELETE `/targets/{name}`** - Delete a registered target
- Requires admin key (if `ECHONET_ADMIN_KEY` is set)
- Returns 404 if target not found

Example:
```bash
curl -X DELETE http://localhost:8123/targets/astraea \
  -H "X-Admin-Key: your-admin-key"
```

### Existing Endpoints (No Breaking Changes)

All existing endpoints remain compatible:
- `POST /register` - Register or update a target
- `GET /targets` - List all registered targets
- `POST /text` - Process text input (uses registered targets)

## Migration Steps

### For New Installations
No action needed! Just start the service and register your targets.

### For Existing Installations

1. **Backup** (optional, but recommended if you want to preserve in-memory state):
   - The old version had no persistence, so there's nothing to migrate
   - Simply re-register your targets after upgrade

2. **Update the code**:
   ```powershell
   git pull
   ```

3. **Restart the service**:
   ```powershell
   # Stop the existing service
   # Then start it again
   uvicorn app.main:app --host 0.0.0.0 --port 8123
   ```

4. **Re-register your targets**:
   ```bash
   # Example: Register Astraea
   curl -X POST http://localhost:8123/register \
     -H "Content-Type: application/json" \
     -H "X-API-Key: your-api-key" \
     -d '{
       "name": "astraea",
       "base_url": "http://astraea.local:9001",
       "phrases": ["hey astraea", "hello astraea"]
     }'
   
   # Example: Register EchoBell
   curl -X POST http://localhost:8123/register \
     -H "Content-Type: application/json" \
     -H "X-API-Key: your-api-key" \
     -d '{
       "name": "echobell",
       "base_url": "http://echobell.local:9000",
       "phrases": ["hey echo", "hello echo bell"]
     }'
   ```

5. **Verify**:
   ```bash
   curl http://localhost:8123/targets -H "X-API-Key: your-api-key"
   ```

## Benefits

✅ **Persistence**: Targets survive service restarts  
✅ **Reliability**: No need to re-register after crashes or updates  
✅ **Auditability**: Database can be backed up, inspected, or migrated  
✅ **Scalability**: SQLite handles concurrent reads efficiently  
✅ **Simplicity**: No external database server required  

## Database Location

The database file is created in the working directory by default:
```
echonet_registry.db
```

**Important**: The database file is excluded from git (in `.gitignore`). Make sure to:
- Back up the database file if needed
- Set appropriate file permissions in production
- Consider using a mounted volume in containerized deployments

## Testing

Run the test script to verify the migration:

```powershell
python test_registry_migration.py
```

This will test:
- ✅ Database initialization
- ✅ Insert/Update (upsert)
- ✅ Retrieval (case-insensitive)
- ✅ Listing all targets
- ✅ Phrase mapping
- ✅ Deletion
- ✅ Persistence across instances

## Troubleshooting

### Database locked errors
If you see "database is locked" errors:
- Ensure only one instance of Echonet is running
- Check file permissions on the database file
- Consider increasing the SQLite timeout (currently uses default)

### Database file permissions
On Linux/Mac, ensure the database file is writable:
```bash
chmod 644 echonet_registry.db
```

### Reset the database
To start fresh, simply delete the database file:
```powershell
Remove-Item echonet_registry.db
```

The database will be recreated automatically on next startup.

## Development Notes

### Registry Class Changes

The `TargetRegistry` class now:
- Accepts a `db_path` parameter in the constructor
- Uses SQLite connections instead of a dict
- Implements proper connection management with context managers
- Stores phrases as JSON in the database

### Code Compatibility

All existing code that uses `TargetRegistry` remains compatible:
- `upsert(target)` - Works the same
- `get(name)` - Works the same (case-insensitive)
- `all()` - Works the same
- `phrase_map()` - Works the same
- **NEW**: `delete(name)` - Delete a target

No changes required in your application code!
