#!/usr/bin/env python3
"""
Test the PUT /state endpoint for state management.
"""

from app.registry import Target, TargetRegistryRepository
from app.state import StateManager
from app.migrations import run_migrations
import os
import tempfile
import json


def test_state_endpoint():
    """Test state update endpoint validation."""
    # Use a temporary database for testing
    test_db = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
    test_db.close()
    
    try:
        print("🧪 Testing PUT /state Endpoint Logic")
        print("=" * 70)
        
        # Run migrations and setup
        print("Setting up database...")
        run_migrations(test_db.name)
        registry = TargetRegistryRepository(db_path=test_db.name)
        state_mgr = StateManager(db_path=test_db.name)
        print("✅ Database setup complete")
        
        # Test 1: Valid state update with existing target
        print("\n📝 Test 1: Valid state update with existing target")
        target = Target(
            name="astraea",
            base_url="http://astraea.local:9001",
            phrases=["hey astraea"]
        )
        registry.upsert(target)
        
        # Simulate the endpoint logic
        update_data = {
            "target": "astraea",
            "source": "llm",
            "state": "active",
            "reason": "Asked a question"
        }
        
        # Verify target exists
        target_check = registry.get(update_data["target"])
        assert target_check is not None, "Target should exist"
        
        # Update state
        state_mgr.set_listen_mode(
            mode=update_data["state"],
            source=f"{update_data['source']}:{update_data['target']}",
            reason=update_data["reason"]
        )
        
        # Verify state changed
        assert state_mgr.get_listen_mode() == "active"
        print("✅ State updated to 'active' for existing target")
        
        # Test 2: Invalid target (should fail)
        print("\n📝 Test 2: Non-existent target should fail")
        invalid_target = registry.get("nonexistent")
        assert invalid_target is None, "Non-existent target should return None"
        print("✅ Non-existent target validation works")
        
        # Test 3: Invalid state value (should fail)
        print("\n📝 Test 3: Invalid state value should fail")
        try:
            state_mgr.set_listen_mode(mode="invalid", source="test", reason="Testing")
            assert False, "Should have raised ValueError"
        except ValueError as e:
            print(f"✅ Invalid state rejected: {e}")
        
        # Test 4: Case-insensitive target lookup
        print("\n📝 Test 4: Case-insensitive target lookup")
        target_upper = registry.get("ASTRAEA")
        assert target_upper is not None
        assert target_upper.name == "astraea"
        print("✅ Case-insensitive target lookup works")
        
        # Test 5: State change history
        print("\n📝 Test 5: Verify state change history")
        history = state_mgr.get_history(name="listen_mode", limit=10)
        assert len(history) >= 2  # Initial + our update
        
        # Find our update in history
        found_update = False
        for change in history:
            if change.source == "llm:astraea" and change.new_value == "active":
                found_update = True
                assert change.reason == "Asked a question"
                print(f"✅ Change logged: {change.old_value} → {change.new_value}")
                print(f"   Source: {change.source}, Reason: {change.reason}")
                break
        
        assert found_update, "State change should be in history"
        
        # Test 6: Multiple targets
        print("\n📝 Test 6: Multiple targets can update state")
        target2 = Target(
            name="echobell",
            base_url="http://echobell.local:9000",
            phrases=["hey echo"]
        )
        registry.upsert(target2)
        
        # Update from different target
        state_mgr.set_listen_mode(
            mode="trigger",
            source="timeout:echobell",
            reason="Session timeout"
        )
        
        assert state_mgr.get_listen_mode() == "trigger"
        print("✅ Multiple targets can update state")
        
        # Test 7: Empty reason handling
        print("\n📝 Test 7: Empty reason handling")
        # Current state from test 6 should be 'trigger'
        current = state_mgr.get_listen_mode()
        print(f"   Current mode before test: {current}")
        
        # Set to opposite of current to ensure a change
        new_mode = "active" if current == "trigger" else "trigger"
        state_mgr.set_listen_mode(
            mode=new_mode,
            source="test7:unique",
            reason=None  # None reason
        )
        
        # Get all history to see what's going on
        all_history = state_mgr.get_history(name="listen_mode", limit=10)
        print(f"   All history ({len(all_history)} entries):")
        for i, h in enumerate(all_history):
            print(f"     [{i}] ID={h.id} {h.changed_at}: {h.old_value} → {h.new_value} (source: {h.source})")
        
        history = state_mgr.get_history(name="listen_mode", limit=1)
        
        # Should still have a source even with None/empty reason
        # History is returned in DESC order, so [0] is the most recent
        assert history[0].source == "test7:unique", f"Expected 'test7:unique', got '{history[0].source}'"
        assert history[0].new_value == new_mode
        print("✅ None reason handled correctly")
        
        print("\n" + "=" * 70)
        print("🎉 All endpoint validation tests passed!")
        
    finally:
        # Cleanup
        import time
        time.sleep(0.1)
        try:
            if os.path.exists(test_db.name):
                os.unlink(test_db.name)
                print(f"🧹 Cleaned up test database")
        except PermissionError:
            print(f"ℹ️  Note: Could not delete test DB (Windows file lock)")


if __name__ == "__main__":
    test_state_endpoint()
