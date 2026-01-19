#!/usr/bin/env python3
"""
Backup and restore utility for Echonet registry database.
"""

import json
import sqlite3
import sys
from datetime import datetime
from pathlib import Path
import argparse


def backup_to_json(db_path: str, output_path: str | None = None):
    """Export registry database to JSON format."""
    if not Path(db_path).exists():
        print(f"❌ Database not found: {db_path}")
        return False
    
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        rows = cursor.execute("SELECT name, base_url, phrases FROM targets ORDER BY name").fetchall()
        
        targets = []
        for row in rows:
            targets.append({
                "name": row["name"],
                "base_url": row["base_url"],
                "phrases": json.loads(row["phrases"])
            })
        
        conn.close()
        
        backup_data = {
            "exported_at": datetime.utcnow().isoformat() + "Z",
            "source_db": db_path,
            "target_count": len(targets),
            "targets": targets
        }
        
        if output_path is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = f"registry_backup_{timestamp}.json"
        
        with open(output_path, "w") as f:
            json.dump(backup_data, f, indent=2)
        
        print(f"✅ Backed up {len(targets)} target(s) to: {output_path}")
        return True
        
    except Exception as e:
        print(f"❌ Error during backup: {e}")
        return False


def restore_from_json(json_path: str, db_path: str, merge: bool = False):
    """Restore registry database from JSON backup."""
    if not Path(json_path).exists():
        print(f"❌ Backup file not found: {json_path}")
        return False
    
    try:
        with open(json_path, "r") as f:
            backup_data = json.load(f)
        
        targets = backup_data.get("targets", [])
        
        if not targets:
            print("⚠️  No targets found in backup file")
            return False
        
        # If not merging, confirm overwrite
        if not merge and Path(db_path).exists():
            response = input(f"⚠️  Database exists. Overwrite? (yes/no): ")
            if response.lower() not in ["yes", "y"]:
                print("❌ Restore cancelled")
                return False
            Path(db_path).unlink()
        
        # Run migrations first to ensure schema is correct
        from app.migrations import run_migrations
        run_migrations(db_path)
        
        # Import using the TargetRegistry class to ensure proper schema
        from app.registry import Target, TargetRegistry
        
        registry = TargetRegistry(db_path=db_path)
        
        for target_data in targets:
            target = Target(
                name=target_data["name"],
                base_url=target_data["base_url"],
                phrases=target_data.get("phrases", [])
            )
            registry.upsert(target)
        
        mode = "merged into" if merge else "restored to"
        print(f"✅ {len(targets)} target(s) {mode}: {db_path}")
        print(f"ℹ️  Backup was created at: {backup_data.get('exported_at', 'unknown')}")
        return True
        
    except Exception as e:
        print(f"❌ Error during restore: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Backup and restore Echonet registry database",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Backup current database
  python backup_registry.py backup

  # Backup to specific file
  python backup_registry.py backup -o my_backup.json

  # Restore from backup (overwrites existing)
  python backup_registry.py restore registry_backup_20260119_120000.json

  # Merge backup into existing database
  python backup_registry.py restore backup.json --merge
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")
    
    # Backup command
    backup_parser = subparsers.add_parser("backup", help="Backup database to JSON")
    backup_parser.add_argument(
        "--db-path",
        default="echonet_registry.db",
        help="Path to the registry database (default: echonet_registry.db)"
    )
    backup_parser.add_argument(
        "-o", "--output",
        help="Output JSON file path (default: auto-generated with timestamp)"
    )
    
    # Restore command
    restore_parser = subparsers.add_parser("restore", help="Restore database from JSON backup")
    restore_parser.add_argument(
        "backup_file",
        help="JSON backup file to restore from"
    )
    restore_parser.add_argument(
        "--db-path",
        default="echonet_registry.db",
        help="Path to the registry database (default: echonet_registry.db)"
    )
    restore_parser.add_argument(
        "--merge",
        action="store_true",
        help="Merge backup into existing database (instead of overwriting)"
    )
    
    args = parser.parse_args()
    
    if args.command == "backup":
        success = backup_to_json(args.db_path, args.output)
        sys.exit(0 if success else 1)
    elif args.command == "restore":
        success = restore_from_json(args.backup_file, args.db_path, args.merge)
        sys.exit(0 if success else 1)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
