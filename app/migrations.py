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
                (2, self._migrate_v2_state_tracking),
                (3, self._migrate_v3_config_settings),
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

    def _migrate_v2_state_tracking(self, conn: sqlite3.Connection) -> None:
        """
        Migration v2: State and settings tracking
        - Create settings table for key-value state (e.g., listen_mode)
        - Create settings_log table for audit trail of state changes
        """
        # Settings table for current state
        conn.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                name TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TEXT NOT NULL DEFAULT (datetime('now')),
                description TEXT
            )
        """)
        
        # Settings log for change history
        conn.execute("""
            CREATE TABLE IF NOT EXISTS settings_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                old_value TEXT,
                new_value TEXT NOT NULL,
                changed_at TEXT NOT NULL DEFAULT (datetime('now')),
                source TEXT,
                reason TEXT
            )
        """)
        
        # Index for efficient log queries
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_settings_log_name 
            ON settings_log(name, changed_at DESC)
        """)
        
        # Initialize default listen_mode setting
        conn.execute("""
            INSERT INTO settings (name, value, description)
            VALUES ('listen_mode', 'trigger', 'Current listening mode: trigger (idle) or active (responding to LLM)')
        """)
        
        # Log the initial setting
        conn.execute("""
            INSERT INTO settings_log (name, old_value, new_value, source, reason)
            VALUES ('listen_mode', NULL, 'trigger', 'migration', 'Initial setup')
        """)
        
        conn.commit()
        log.info("Created state tracking: settings, settings_log tables with default listen_mode")

    def _migrate_v3_config_settings(self, conn: sqlite3.Connection) -> None:
        """
        Migration v3: Configuration settings
        - Create config table for runtime configuration
        - Separate from settings table (which is for state like listen_mode)
        - Initialize default configuration values
        """
        # Config table for runtime configuration
        conn.execute("""
            CREATE TABLE IF NOT EXISTS config (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                type TEXT NOT NULL CHECK(type IN ('bool', 'int', 'float', 'str')),
                description TEXT,
                updated_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
        """)
        
        # Index for efficient lookups
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_config_key 
            ON config(key)
        """)
        
        # Initialize default configuration values
        default_configs = [
            ('enable_preroll_buffer', 'false', 'bool', 'Enable pre-roll audio buffering (capture audio before trigger)'),
            ('preroll_buffer_seconds', '2.0', 'float', 'Seconds of audio to buffer before trigger event'),
        ]
        
        for key, value, value_type, description in default_configs:
            conn.execute("""
                INSERT INTO config (key, value, type, description)
                VALUES (?, ?, ?, ?)
            """, (key, value, value_type, description))
        
        conn.commit()
        log.info("Created config table with default values (preroll_buffer settings)")


def run_migrations(db_path: str | Path) -> None:
    """
    Run database migrations.
    Called on application startup.
    """
    manager = MigrationManager(db_path)
    manager.run_migrations()
