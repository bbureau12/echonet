#!/usr/bin/env python3
"""
Manual database migration tool for Echonet.

This script can be used to:
- Run migrations manually
- Check current schema version
- View migration history

Migrations are normally run automatically on application startup,
but this tool is useful for troubleshooting or manual database management.
"""

import argparse
import logging
import sqlite3
import sys
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)


def check_schema_version(db_path: str):
    """Display current schema version and migration history."""
    if not Path(db_path).exists():
        print(f"❌ Database not found: {db_path}")
        print("ℹ️  Database will be created on first application startup.")
        return
    
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        
        # Check if schema_version table exists
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='schema_version'"
        )
        if not cursor.fetchone():
            print(f"📊 Database: {db_path}")
            print("⚠️  No schema_version table found (pre-migration database or empty)")
            conn.close()
            return
        
        # Get current version
        cursor = conn.execute("SELECT version FROM schema_version ORDER BY version DESC LIMIT 1")
        row = cursor.fetchone()
        current_version = row[0] if row else 0
        
        # Get migration history
        cursor = conn.execute("SELECT version, applied_at FROM schema_version ORDER BY version")
        history = cursor.fetchall()
        
        print(f"📊 Database: {db_path}")
        print(f"📌 Current Schema Version: v{current_version}")
        print(f"\n🕐 Migration History:")
        print("=" * 60)
        
        if history:
            for row in history:
                print(f"  v{row['version']:2d} - Applied at: {row['applied_at']}")
        else:
            print("  (No migrations applied yet)")
        
        # Show table info
        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        tables = [row[0] for row in cursor.fetchall()]
        
        print(f"\n📋 Tables ({len(tables)}):")
        for table in tables:
            cursor = conn.execute(f"SELECT COUNT(*) FROM {table}")
            count = cursor.fetchone()[0]
            print(f"  - {table:20s} ({count} rows)")
        
        conn.close()
        
    except Exception as e:
        print(f"❌ Error reading database: {e}")
        sys.exit(1)


def run_migrations_manually(db_path: str):
    """Run database migrations manually."""
    print(f"🔧 Running migrations on: {db_path}")
    print("=" * 60)
    
    try:
        from app.migrations import run_migrations
        run_migrations(db_path)
        print("\n✅ Migrations completed successfully")
        print("\nRun with --status to view the updated schema version.")
        
    except Exception as e:
        print(f"❌ Error running migrations: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description="Echonet database migration tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Check current schema version
  python migrate_db.py --status

  # Run migrations manually (normally done on startup)
  python migrate_db.py --migrate

  # Use custom database path
  python migrate_db.py --db-path ./data/registry.db --status
        """
    )
    
    parser.add_argument(
        "--db-path",
        default="echonet_registry.db",
        help="Path to the registry database (default: echonet_registry.db)"
    )
    
    action_group = parser.add_mutually_exclusive_group(required=True)
    action_group.add_argument(
        "--status",
        action="store_true",
        help="Show current schema version and migration history"
    )
    action_group.add_argument(
        "--migrate",
        action="store_true",
        help="Run pending migrations"
    )
    
    args = parser.parse_args()
    
    if args.status:
        check_schema_version(args.db_path)
    elif args.migrate:
        run_migrations_manually(args.db_path)


if __name__ == "__main__":
    main()
