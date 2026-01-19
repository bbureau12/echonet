# SQLite Registry Migration - Summary

## Changes Made

This migration converts the Echonet target registry from in-memory storage to a persistent SQLite database.

### Modified Files

1. **`app/registry.py`**
   - Added SQLite database backend
   - Implemented `_init_db()` for schema creation
   - Converted `upsert()`, `get()`, `all()`, and `phrase_map()` to use SQLite
   - Added new `delete()` method for removing targets
   - Phrases stored as JSON in the database
   - Case-insensitive lookups via SQL COLLATE NOCASE

2. **`app/settings.py`**
   - Added `db_path` setting (default: `"echonet_registry.db"`)
   - Configurable via `ECHONET_DB_PATH` environment variable

3. **`app/main.py`**
   - Updated `TargetRegistry` initialization to use `settings.db_path`
   - Added `DELETE /targets/{name}` endpoint for target deletion
   - Requires admin key for deletion (like registration)

4. **`.gitignore`**
   - Added database file exclusions:
     - `echonet_registry.db`
     - `echonet_registry.db-journal`
     - `echonet_registry.db-wal`
     - `echonet_registry.db-shm`

### New Files

1. **`MIGRATION_SQLITE.md`**
   - Comprehensive migration guide
   - API documentation
   - Troubleshooting tips
   - Benefits and configuration details

2. **`test_registry_migration.py`**
   - Automated test suite for the SQLite implementation
   - Tests all CRUD operations
   - Validates persistence across instances
   - Case-insensitivity tests

3. **`inspect_registry.py`**
   - CLI tool to inspect the database contents
   - Shows all registered targets and their phrases
   - Database statistics

## Database Schema

```sql
CREATE TABLE targets (
    name TEXT PRIMARY KEY,
    base_url TEXT NOT NULL,
    phrases TEXT NOT NULL  -- JSON array
);

CREATE INDEX idx_target_name ON targets(name COLLATE NOCASE);
```

## Key Features

✅ **Zero Breaking Changes**: All existing code remains compatible  
✅ **Persistence**: Registrations survive service restarts  
✅ **Case-Insensitive**: Target lookups work regardless of case  
✅ **Atomic Operations**: SQLite ensures data consistency  
✅ **No Dependencies**: Uses Python's built-in sqlite3 module  
✅ **Thread-Safe**: Proper connection management  
✅ **Configurable**: Database path via environment variable  

## Testing

```powershell
# Run the test suite
python test_registry_migration.py

# Inspect the database
python inspect_registry.py
```

## Usage Examples

### Register a Target (Unchanged API)
```bash
curl -X POST http://localhost:8123/register \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key" \
  -d '{
    "name": "astraea",
    "base_url": "http://astraea.local:9001",
    "phrases": ["hey astraea", "hello astraea"]
  }'
```

### Delete a Target (NEW)
```bash
curl -X DELETE http://localhost:8123/targets/astraea \
  -H "X-API-Key: your-api-key" \
  -H "X-Admin-Key: your-admin-key"
```

### List All Targets (Unchanged API)
```bash
curl http://localhost:8123/targets \
  -H "X-API-Key: your-api-key"
```

## Migration Path

For existing installations:
1. Update the code (git pull)
2. Restart the service
3. Re-register your targets (they were in-memory before, so lost on restart anyway)

That's it! No data migration needed since the old version didn't persist data.

## Next Steps

Consider adding:
- Database backup scripts
- Target import/export functionality
- Admin UI for managing targets
- Database migration tools for future schema changes
