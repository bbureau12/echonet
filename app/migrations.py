"""
Database migrations for Echonet registry.

This module handles schema initialization and future migrations.
Migrations are run automatically on application startup.
"""

from __future__ import annotations

import logging
import sqlite3
from pathlib import Path

log = logging.getLogger("echonet.migrations")


class MigrationManager:
    """Manages database schema migrations."""
    
    def __init__(self, db_path: str | Path):
        self.db_path = str(db_path)
    
    def _get_connection(self) -> sqlite3.Connection:
        """Get a database connection."""
        return sqlite3.connect(self.db_path)
    
    def _get_schema_version(self, conn: sqlite3.Connection) -> int:
        """Get current schema version from database."""
        try:
            cursor = conn.execute("SELECT version FROM schema_version ORDER BY version DESC LIMIT 1")
            row = cursor.fetchone()
            return row[0] if row else 0
        except sqlite3.OperationalError:
            # Table doesn't exist yet
            return 0
    
    def _set_schema_version(self, conn: sqlite3.Connection, version: int) -> None:
        """Record a schema version."""
        conn.execute("INSERT INTO schema_version (version, applied_at) VALUES (?, datetime('now'))", (version,))
        conn.commit()
    
    def run_migrations(self) -> None:
        """Run all pending migrations."""
        with self._get_connection() as conn:
            current_version = self._get_schema_version(conn)
            log.info(f"Current schema version: {current_version}")
            
            # Run migrations in order
            migrations = [
                (1, self._migrate_v1_initial_schema),
            ]
            
            for version, migration_func in migrations:
                if current_version < version:
                    log.info(f"Running migration v{version}: {migration_func.__name__}")
                    migration_func(conn)
                    self._set_schema_version(conn, version)
                    log.info(f"✅ Migration v{version} completed")
            
            final_version = self._get_schema_version(conn)
            if final_version == current_version:
                log.info("Database schema is up to date")
            else:
                log.info(f"Database migrated from v{current_version} to v{final_version}")
    
    def _migrate_v1_initial_schema(self, conn: sqlite3.Connection) -> None:
        """
        Migration v1: Initial schema
        - Create schema_version table
        - Create targets table
        - Create index on target name
        """
        # Schema version tracking
        conn.execute("""
            CREATE TABLE IF NOT EXISTS schema_version (
                version INTEGER PRIMARY KEY,
                applied_at TEXT NOT NULL
            )
        """)
        
        # Targets table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS targets (
                name TEXT PRIMARY KEY,
                base_url TEXT NOT NULL,
                phrases TEXT NOT NULL
            )
        """)
        
        # Index for case-insensitive lookups
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_target_name 
            ON targets(name COLLATE NOCASE)
        """)
        
        conn.commit()
        log.info("Created initial schema: schema_version, targets, indexes")


def run_migrations(db_path: str | Path) -> None:
    """
    Run database migrations.
    Called on application startup.
    """
    manager = MigrationManager(db_path)
    manager.run_migrations()
