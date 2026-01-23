"""
Tests for inactive mode (not recording).
"""
import pytest
import asyncio
from pathlib import Path
from app.state import StateManager
from app.migrations import run_migrations


class TestInactiveMode:
    """Test inactive mode behavior."""
    
    def test_inactive_mode_state(self, tmp_path):
        """Test that inactive mode can be set and retrieved."""
        db_path = tmp_path / "test_state.db"
        run_migrations(str(db_path))
        
        state = StateManager(db_path=db_path)
        
        # Set to inactive
        state.set_listen_mode("inactive", source="test", reason="Testing inactive mode")
        
        # Verify mode is inactive
        assert state.get_listen_mode() == "inactive"
        assert state.is_inactive_mode()
        assert not state.is_trigger_mode()
        assert not state.is_active_mode()
    
    def test_invalid_mode_raises_error(self, tmp_path):
        """Test that invalid mode raises ValueError."""
        db_path = tmp_path / "test_state.db"
        run_migrations(str(db_path))
        
        state = StateManager(db_path=db_path)
        
        with pytest.raises(ValueError, match="Invalid listen_mode"):
            state.set_listen_mode("invalid_mode", source="test")
    
    def test_mode_transitions(self, tmp_path):
        """Test transitions between all three modes."""
        db_path = tmp_path / "test_state.db"
        run_migrations(str(db_path))
        
        state = StateManager(db_path=db_path)
        
        # Start in trigger (default)
        assert state.get_listen_mode() == "trigger"
        
        # Switch to inactive
        state.set_listen_mode("inactive", source="test", reason="Disable recording")
        assert state.is_inactive_mode()
        
        # Switch to active
        state.set_listen_mode("active", source="test", reason="Button pressed")
        assert state.is_active_mode()
        
        # Switch back to trigger
        state.set_listen_mode("trigger", source="test", reason="Auto-reset")
        assert state.is_trigger_mode()
        
        # Back to inactive
        state.set_listen_mode("inactive", source="test", reason="Privacy mode")
        assert state.is_inactive_mode()
