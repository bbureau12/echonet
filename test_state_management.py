#!/usr/bin/env python3
"""
Test script for state management functionality.
"""

from app.state import StateManager
from app.migrations import run_migrations
import os
import tempfile


def test_state_manager():
    """Test state management operations."""
    # Use a temporary database for testing
    test_db = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
    test_db.close()
    
    try:
        print("🧪 Testing State Management")
        print("=" * 70)
        
        # Run migrations first
        print("Running migrations...")
        run_migrations(test_db.name)
        print("✅ Migrations completed")
        
        # Initialize state manager
        state = StateManager(db_path=test_db.name)
        print("✅ State manager initialized")
        
        # Test default listen_mode from migration
        mode = state.get_listen_mode()
        assert mode == "trigger", f"Expected 'trigger', got '{mode}'"
        print(f"✅ Default listen_mode: {mode}")
        
        # Test convenience methods
        assert state.is_trigger_mode() is True
        assert state.is_active_mode() is False
        print("✅ Convenience methods work")
        
        # Test setting listen_mode to active
        state.set_listen_mode("active", source="test", reason="Testing active mode")
        mode = state.get_listen_mode()
        assert mode == "active"
        assert state.is_active_mode() is True
        assert state.is_trigger_mode() is False
        print("✅ Set listen_mode to 'active'")
        
        # Test setting back to trigger
        state.set_listen_mode("trigger", source="test", reason="Testing trigger mode")
        mode = state.get_listen_mode()
        assert mode == "trigger"
        print("✅ Set listen_mode back to 'trigger'")
        
        # Test invalid mode
        try:
            state.set_listen_mode("invalid")
            assert False, "Should have raised ValueError"
        except ValueError as e:
            print(f"✅ Invalid mode rejected: {e}")
        
        # Test setting custom state
        state.set("custom_setting", "value1", source="test", reason="Initial value")
        value = state.get_value("custom_setting")
        assert value == "value1"
        print("✅ Custom setting created")
        
        # Test updating custom state
        state.set("custom_setting", "value2", source="test", reason="Updated value")
        value = state.get_value("custom_setting")
        assert value == "value2"
        print("✅ Custom setting updated")
        
        # Test that identical updates don't create log entries
        state.set("custom_setting", "value2", source="test", reason="No change")
        history = state.get_history(name="custom_setting")
        # Should have 2 entries (initial + update), not 3
        assert len(history) == 2, f"Expected 2 history entries, got {len(history)}"
        print("✅ Duplicate values don't create log entries")
        
        # Test getting all settings
        all_settings = state.all()
        assert len(all_settings) >= 2  # listen_mode + custom_setting
        print(f"✅ Retrieved all settings: {len(all_settings)} settings")
        for s in all_settings:
            print(f"   - {s.name} = {s.value}")
        
        # Test get full setting object
        setting = state.get("listen_mode")
        assert setting is not None
        assert setting.name == "listen_mode"
        assert setting.value == "trigger"
        assert setting.description is not None
        print("✅ Get full setting object works")
        
        # Test get non-existent setting
        setting = state.get("nonexistent")
        assert setting is None
        value = state.get_value("nonexistent", default="default_val")
        assert value == "default_val"
        print("✅ Non-existent setting returns None/default")
        
        # Test getting all history
        all_history = state.get_history(limit=100)
        print(f"✅ Retrieved complete history: {len(all_history)} changes")
        
        # Verify history for listen_mode
        listen_history = state.get_history(name="listen_mode", limit=10)
        # Should have: migration init, active, trigger = 3 entries
        assert len(listen_history) == 3, f"Expected 3 history entries, got {len(listen_history)}"
        print(f"✅ Listen mode change history: {len(listen_history)} entries")
        
        print("\n📊 Listen Mode Change History:")
        for change in listen_history:
            print(f"   {change.changed_at}: {change.old_value} → {change.new_value}")
            print(f"      Source: {change.source}, Reason: {change.reason}")
        
        # Test persistence across instances
        state2 = StateManager(db_path=test_db.name)
        mode = state2.get_listen_mode()
        assert mode == "trigger"
        custom = state2.get_value("custom_setting")
        assert custom == "value2"
        print("✅ Persistence across instances works")
        
        print("=" * 70)
        print("🎉 All state management tests passed!")
        
    finally:
        # Cleanup
        import time
        time.sleep(0.1)
        try:
            if os.path.exists(test_db.name):
                os.unlink(test_db.name)
                print(f"🧹 Cleaned up test database: {test_db.name}")
        except PermissionError:
            print(f"ℹ️  Note: Could not delete test DB (Windows file lock). File: {test_db.name}")


if __name__ == "__main__":
    test_state_manager()
