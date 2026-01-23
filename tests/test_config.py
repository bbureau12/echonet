"""
Tests for configuration management system.
"""

import pytest
from app.state import StateManager
from app.migrations import run_migrations
import tempfile
import os


@pytest.fixture
def state_manager():
    """Create a StateManager with a temporary database."""
    fd, db_path = tempfile.mkstemp(suffix='.db')
    os.close(fd)
    
    try:
        # Run migrations to create schema
        run_migrations(db_path)
        
        # Create state manager
        yield StateManager(db_path)
    finally:
        # Cleanup
        if os.path.exists(db_path):
            try:
                os.unlink(db_path)
            except PermissionError:
                # Windows file locking issue - not critical for tests
                pass


def test_get_config(state_manager):
    """Test retrieving a configuration setting."""
    config = state_manager.get_config('enable_preroll_buffer')
    
    assert config is not None
    assert config['key'] == 'enable_preroll_buffer'
    assert config['value'] == 'false'  # Default value
    assert config['type'] == 'bool'
    assert 'description' in config
    assert 'updated_at' in config


def test_get_all_config(state_manager):
    """Test retrieving all configuration settings."""
    all_config = state_manager.get_all_config()
    
    assert isinstance(all_config, dict)
    assert len(all_config) >= 2  # At least enable_preroll_buffer and preroll_buffer_seconds
    assert 'enable_preroll_buffer' in all_config
    assert 'preroll_buffer_seconds' in all_config


def test_set_config_bool(state_manager):
    """Test setting a boolean configuration value."""
    # Set to true
    state_manager.set_config('enable_preroll_buffer', 'true')
    config = state_manager.get_config('enable_preroll_buffer')
    assert config['value'] == 'true'
    
    # Set to false
    state_manager.set_config('enable_preroll_buffer', 'false')
    config = state_manager.get_config('enable_preroll_buffer')
    assert config['value'] == 'false'


def test_set_config_float(state_manager):
    """Test setting a float configuration value."""
    state_manager.set_config('preroll_buffer_seconds', '3.5')
    config = state_manager.get_config('preroll_buffer_seconds')
    assert config['value'] == '3.5'


def test_set_config_invalid_key(state_manager):
    """Test setting a non-existent configuration key."""
    with pytest.raises(ValueError, match="Configuration key .* does not exist"):
        state_manager.set_config('nonexistent_key', 'value')


def test_set_config_invalid_bool(state_manager):
    """Test setting an invalid boolean value."""
    with pytest.raises(ValueError, match="Boolean value must be"):
        state_manager.set_config('enable_preroll_buffer', 'yes')
    
    with pytest.raises(ValueError, match="Boolean value must be"):
        state_manager.set_config('enable_preroll_buffer', '1')


def test_set_config_invalid_float(state_manager):
    """Test setting an invalid float value."""
    with pytest.raises(ValueError, match="Invalid value"):
        state_manager.set_config('preroll_buffer_seconds', 'not_a_number')


def test_get_config_bool(state_manager):
    """Test get_config_bool helper method."""
    # Test default
    assert state_manager.get_config_bool('enable_preroll_buffer') == False
    
    # Set to true
    state_manager.set_config('enable_preroll_buffer', 'true')
    assert state_manager.get_config_bool('enable_preroll_buffer') == True
    
    # Set to false
    state_manager.set_config('enable_preroll_buffer', 'false')
    assert state_manager.get_config_bool('enable_preroll_buffer') == False
    
    # Test default for non-existent key
    assert state_manager.get_config_bool('nonexistent', default=True) == True


def test_get_config_float(state_manager):
    """Test get_config_float helper method."""
    # Test default
    default_val = state_manager.get_config_float('preroll_buffer_seconds')
    assert default_val == 2.0
    
    # Set new value
    state_manager.set_config('preroll_buffer_seconds', '5.5')
    assert state_manager.get_config_float('preroll_buffer_seconds') == 5.5
    
    # Test default for non-existent key
    assert state_manager.get_config_float('nonexistent', default=3.14) == 3.14


def test_config_persistence(state_manager):
    """Test that configuration changes persist."""
    # Set value
    state_manager.set_config('enable_preroll_buffer', 'true')
    
    # Get value back
    config = state_manager.get_config('enable_preroll_buffer')
    assert config['value'] == 'true'
    
    # Verify it's actually in the database
    with state_manager._get_connection() as conn:
        row = conn.execute(
            "SELECT value FROM config WHERE key = ?",
            ('enable_preroll_buffer',)
        ).fetchone()
        assert row['value'] == 'true'
