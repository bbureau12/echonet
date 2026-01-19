from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Target:
    name: str
    base_url: str
    phrases: list[str] = field(default_factory=list)

    @property
    def listen_url(self) -> str:
        return self.base_url.rstrip("/") + "/listen"


class TargetRegistry:
    def __init__(self, db_path: str | Path = "echonet_registry.db"):
        """
        Initialize the target registry.
        
        Note: Schema migrations should be run via migrations.run_migrations()
        before creating the registry instance.
        """
        self.db_path = str(db_path)

    def _get_connection(self) -> sqlite3.Connection:
        """Get a database connection."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def upsert(self, t: Target) -> None:
        """Insert or update a target in the database."""
        phrases_json = json.dumps(t.phrases)
        with self._get_connection() as conn:
            conn.execute("""
                INSERT INTO targets (name, base_url, phrases)
                VALUES (?, ?, ?)
                ON CONFLICT(name) DO UPDATE SET
                    base_url = excluded.base_url,
                    phrases = excluded.phrases
            """, (t.name.lower(), t.base_url, phrases_json))
            conn.commit()

    def get(self, name: str) -> Target | None:
        """Retrieve a target by name."""
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT name, base_url, phrases FROM targets WHERE name = ? COLLATE NOCASE",
                (name.lower(),)
            ).fetchone()
            
            if row is None:
                return None
            
            phrases = json.loads(row["phrases"])
            return Target(name=row["name"], base_url=row["base_url"], phrases=phrases)

    def all(self) -> list[Target]:
        """Retrieve all targets."""
        with self._get_connection() as conn:
            rows = conn.execute("SELECT name, base_url, phrases FROM targets").fetchall()
            
            targets = []
            for row in rows:
                phrases = json.loads(row["phrases"])
                targets.append(Target(name=row["name"], base_url=row["base_url"], phrases=phrases))
            
            return targets

    def delete(self, name: str) -> bool:
        """Delete a target by name. Returns True if deleted, False if not found."""
        with self._get_connection() as conn:
            cursor = conn.execute("DELETE FROM targets WHERE name = ? COLLATE NOCASE", (name.lower(),))
            conn.commit()
            return cursor.rowcount > 0

    def phrase_map(self) -> list[tuple[str, str]]:
        """
        Returns a list of (phrase, target_name) for trigger matching.
        """
        out: list[tuple[str, str]] = []
        for t in self.all():
            for p in t.phrases:
                p2 = p.strip().lower()
                if p2:
                    out.append((p2, t.name.lower()))
        return out
