#!/usr/bin/env python3
"""
State inspection tool for Echonet.
View current application state and change history.
"""

import argparse
import sys
from pathlib import Path


def inspect_state(db_path: str = "echonet_registry.db"):
    """Display current application state."""
    if not Path(db_path).exists():
        print(f"❌ Database not found: {db_path}")
        print(f"ℹ️  Run the application first to create the database.")
        return
    
    try:
        from app.state import StateManager
        
        state = StateManager(db_path=db_path)
        
        # Get all settings
        settings = state.all()
        
        if not settings:
            print(f"📭 No state settings found in {db_path}")
            return
        
        print(f"📊 Echonet Application State: {db_path}")
        print("=" * 70)
        
        for s in settings:
            print(f"\n🔹 {s.name.upper()}")
            print(f"   Value: {s.value}")
            print(f"   Updated: {s.updated_at}")
            if s.description:
                print(f"   Description: {s.description}")
        
        print("\n" + "=" * 70)
        print(f"Total Settings: {len(settings)}")
        
        # Show current listen mode prominently
        listen_mode = state.get_listen_mode()
        mode_icon = "🎯" if listen_mode == "trigger" else "🎙️"
        print(f"\n{mode_icon} Current Listen Mode: {listen_mode.upper()}")
        
    except Exception as e:
        print(f"❌ Error reading state: {e}")
        sys.exit(1)


def inspect_history(db_path: str = "echonet_registry.db", setting_name: str = None, limit: int = 20):
    """Display state change history."""
    if not Path(db_path).exists():
        print(f"❌ Database not found: {db_path}")
        return
    
    try:
        from app.state import StateManager
        
        state = StateManager(db_path=db_path)
        
        # Get history
        changes = state.get_history(name=setting_name, limit=limit)
        
        if not changes:
            filter_msg = f" for '{setting_name}'" if setting_name else ""
            print(f"📭 No change history found{filter_msg}")
            return
        
        title = f"Change History: {setting_name}" if setting_name else "Complete Change History"
        print(f"📜 {title}")
        print("=" * 70)
        
        for change in changes:
            old = change.old_value if change.old_value else "(none)"
            print(f"\n[{change.id}] {change.changed_at}")
            print(f"   Setting: {change.name}")
            print(f"   Change: {old} → {change.new_value}")
            if change.source:
                print(f"   Source: {change.source}")
            if change.reason:
                print(f"   Reason: {change.reason}")
        
        print("\n" + "=" * 70)
        print(f"Total Changes: {len(changes)}")
        
        if len(changes) == limit:
            print(f"ℹ️  Showing most recent {limit} changes. Use --limit to see more.")
        
    except Exception as e:
        print(f"❌ Error reading history: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description="Echonet state inspection tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # View current state
  python inspect_state.py

  # View change history
  python inspect_state.py --history

  # View history for specific setting
  python inspect_state.py --history --setting listen_mode

  # View more history entries
  python inspect_state.py --history --limit 50

  # Use custom database path
  python inspect_state.py --db-path ./data/registry.db
        """
    )
    
    parser.add_argument(
        "--db-path",
        default="echonet_registry.db",
        help="Path to the registry database (default: echonet_registry.db)"
    )
    
    parser.add_argument(
        "--history",
        action="store_true",
        help="Show change history instead of current state"
    )
    
    parser.add_argument(
        "--setting",
        help="Filter history by setting name (requires --history)"
    )
    
    parser.add_argument(
        "--limit",
        type=int,
        default=20,
        help="Number of history entries to show (default: 20)"
    )
    
    args = parser.parse_args()
    
    if args.setting and not args.history:
        print("❌ Error: --setting requires --history")
        sys.exit(1)
    
    if args.history:
        inspect_history(args.db_path, setting_name=args.setting, limit=args.limit)
    else:
        inspect_state(args.db_path)


if __name__ == "__main__":
    main()
