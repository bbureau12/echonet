#!/usr/bin/env python3
"""
Database inspection tool for Echonet registry.
Displays all registered targets and their activation phrases.
"""

import json
import sqlite3
import sys
from pathlib import Path


def inspect_registry(db_path: str = "echonet_registry.db"):
    """Display all targets in the registry database."""
    if not Path(db_path).exists():
        print(f"❌ Database not found: {db_path}")
        print(f"ℹ️  The database will be created when you register the first target.")
        return
    
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Get all targets
        rows = cursor.execute("SELECT name, base_url, phrases FROM targets ORDER BY name").fetchall()
        
        if not rows:
            print(f"📭 No targets registered in {db_path}")
            return
        
        print(f"📊 Echonet Registry Database: {db_path}")
        print("=" * 70)
        
        for i, row in enumerate(rows, 1):
            phrases = json.loads(row["phrases"])
            print(f"\n{i}. {row['name'].upper()}")
            print(f"   Base URL: {row['base_url']}")
            print(f"   Listen URL: {row['base_url'].rstrip('/')}/listen")
            print(f"   Activation Phrases ({len(phrases)}):")
            for phrase in phrases:
                print(f"      • {phrase}")
        
        print("\n" + "=" * 70)
        print(f"Total Targets: {len(rows)}")
        
        # Get database size
        db_size = Path(db_path).stat().st_size
        print(f"Database Size: {db_size:,} bytes")
        
        conn.close()
        
    except Exception as e:
        print(f"❌ Error reading database: {e}")
        sys.exit(1)


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Inspect Echonet registry database")
    parser.add_argument(
        "--db-path",
        default="echonet_registry.db",
        help="Path to the registry database (default: echonet_registry.db)"
    )
    
    args = parser.parse_args()
    inspect_registry(args.db_path)
