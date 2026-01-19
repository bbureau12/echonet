"""
State management for Echonet.

Manages application state like listen_mode (trigger vs active listening)
with automatic change logging for audit trail.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class Setting:
    """Represents a single setting/state value."""
    name: str
    value: str
    updated_at: str
    description: Optional[str] = None


@dataclass
class SettingChange:
    """Represents a logged setting change."""
    id: int
    name: str
    old_value: Optional[str]
    new_value: str
    changed_at: str
    source: Optional[str]
    reason: Optional[str]


class StateManager:
    """Manages application state with change tracking."""
    
    def __init__(self, db_path: str | Path = "echonet_registry.db"):
        """
        Initialize the state manager.
        
        Note: Schema migrations should be run via migrations.run_migrations()
        before creating the StateManager instance.
        """
        self.db_path = str(db_path)
    
    def _get_connection(self) -> sqlite3.Connection:
        """Get a database connection."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def get(self, name: str) -> Optional[Setting]:
        """Get a setting by name."""
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT name, value, updated_at, description FROM settings WHERE name = ?",
                (name,)
            ).fetchone()
            
            if row is None:
                return None
            
            return Setting(
                name=row["name"],
                value=row["value"],
                updated_at=row["updated_at"],
                description=row["description"]
            )
    
    def get_value(self, name: str, default: Optional[str] = None) -> Optional[str]:
        """Get just the value of a setting, with optional default."""
        setting = self.get(name)
        return setting.value if setting else default
    
    def set(
        self,
        name: str,
        value: str,
        source: Optional[str] = None,
        reason: Optional[str] = None,
        description: Optional[str] = None
    ) -> None:
        """
        Set a setting value and log the change.
        
        Args:
            name: Setting name
            value: New value
            source: What triggered the change (e.g., 'api', 'user', 'llm_response')
            reason: Why the change was made
            description: Description of the setting (only used for new settings)
        """
        with self._get_connection() as conn:
            # Get old value if it exists
            old_value = self.get_value(name)
            
            # Don't log if value hasn't changed
            if old_value == value:
                return
            
            # Upsert the setting
            conn.execute("""
                INSERT INTO settings (name, value, updated_at, description)
                VALUES (?, ?, datetime('now'), ?)
                ON CONFLICT(name) DO UPDATE SET
                    value = excluded.value,
                    updated_at = excluded.updated_at,
                    description = COALESCE(excluded.description, description)
            """, (name, value, description))
            
            # Log the change
            conn.execute("""
                INSERT INTO settings_log (name, old_value, new_value, changed_at, source, reason)
                VALUES (?, ?, ?, datetime('now'), ?, ?)
            """, (name, old_value, value, source, reason))
            
            conn.commit()
    
    def all(self) -> list[Setting]:
        """Get all settings."""
        with self._get_connection() as conn:
            rows = conn.execute(
                "SELECT name, value, updated_at, description FROM settings ORDER BY name"
            ).fetchall()
            
            return [
                Setting(
                    name=row["name"],
                    value=row["value"],
                    updated_at=row["updated_at"],
                    description=row["description"]
                )
                for row in rows
            ]
    
    def get_history(
        self,
        name: Optional[str] = None,
        limit: int = 100
    ) -> list[SettingChange]:
        """
        Get setting change history.
        
        Args:
            name: Filter by setting name (None = all settings)
            limit: Maximum number of records to return
        """
        with self._get_connection() as conn:
            if name:
                query = """
                    SELECT id, name, old_value, new_value, changed_at, source, reason
                    FROM settings_log
                    WHERE name = ?
                    ORDER BY changed_at DESC, id DESC
                    LIMIT ?
                """
                rows = conn.execute(query, (name, limit)).fetchall()
            else:
                query = """
                    SELECT id, name, old_value, new_value, changed_at, source, reason
                    FROM settings_log
                    ORDER BY changed_at DESC, id DESC
                    LIMIT ?
                """
                rows = conn.execute(query, (limit,)).fetchall()
            
            return [
                SettingChange(
                    id=row["id"],
                    name=row["name"],
                    old_value=row["old_value"],
                    new_value=row["new_value"],
                    changed_at=row["changed_at"],
                    source=row["source"],
                    reason=row["reason"]
                )
                for row in rows
            ]
    
    # Convenience methods for listen_mode
    
    def get_listen_mode(self) -> str:
        """Get current listen mode. Returns 'trigger' or 'active'."""
        return self.get_value("listen_mode", default="trigger")
    
    def set_listen_mode(
        self,
        mode: str,
        source: Optional[str] = None,
        reason: Optional[str] = None
    ) -> None:
        """
        Set listen mode to 'trigger' (idle) or 'active' (responding to LLM).
        
        Args:
            mode: Either 'trigger' or 'active'
            source: What triggered the mode change
            reason: Why the mode changed
        """
        if mode not in ("trigger", "active"):
            raise ValueError(f"Invalid listen_mode: {mode}. Must be 'trigger' or 'active'")
        
        self.set("listen_mode", mode, source=source, reason=reason)
    
    def is_trigger_mode(self) -> bool:
        """Check if currently in trigger (idle) mode."""
        return self.get_listen_mode() == "trigger"
    
    def is_active_mode(self) -> bool:
        """Check if currently in active listening mode."""
        return self.get_listen_mode() == "active"
