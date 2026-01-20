"""Test audio device management."""

import pytest
from unittest.mock import Mock, patch
from app.audio_io import list_audio_devices, get_default_device, AudioDevice


def test_audio_device_dataclass():
    """Test AudioDevice dataclass creation."""
    device = AudioDevice(
        index=0,
        name="Test Microphone",
        channels=2,
        sample_rate=48000.0,
        is_default=True
    )
    
    assert device.index == 0
    assert device.name == "Test Microphone"
    assert device.channels == 2
    assert device.sample_rate == 48000.0
    assert device.is_default is True


@patch('sounddevice.query_devices')
@patch('sounddevice.default')
def test_list_audio_devices(mock_default, mock_query):
    """Test listing audio input devices."""
    # Mock sounddevice responses
    mock_default.device = [0, 1]  # (input, output)
    mock_query.return_value = [
        {
            'name': 'Microphone 1',
            'max_input_channels': 2,
            'max_output_channels': 0,
            'default_samplerate': 48000.0
        },
        {
            'name': 'Speakers',
            'max_input_channels': 0,
            'max_output_channels': 2,
            'default_samplerate': 48000.0
        },
        {
            'name': 'USB Microphone',
            'max_input_channels': 1,
            'max_output_channels': 0,
            'default_samplerate': 44100.0
        }
    ]
    
    devices = list_audio_devices()
    
    # Should only include input devices (max_input_channels > 0)
    assert len(devices) == 2
    assert devices[0].name == 'Microphone 1'
    assert devices[0].is_default is True  # index 0 matches default
    assert devices[1].name == 'USB Microphone'
    assert devices[1].is_default is False


@patch('sounddevice.query_devices')
@patch('sounddevice.default')
def test_get_default_device(mock_default, mock_query):
    """Test getting the system default audio device."""
    mock_default.device = [2, 1]  # (input, output)
    mock_query.return_value = {
        'name': 'Default Microphone',
        'max_input_channels': 2,
        'max_output_channels': 0,
        'default_samplerate': 48000.0
    }
    
    device = get_default_device()
    
    assert device is not None
    assert device.index == 2
    assert device.name == 'Default Microphone'
    assert device.is_default is True


@patch('sounddevice.query_devices')
@patch('sounddevice.default')
def test_get_default_device_no_input(mock_default, mock_query):
    """Test when default device has no input channels."""
    mock_default.device = [0, 1]
    mock_query.return_value = {
        'name': 'Speakers Only',
        'max_input_channels': 0,  # No input!
        'max_output_channels': 2,
        'default_samplerate': 48000.0
    }
    
    device = get_default_device()
    
    assert device is None


def test_state_manager_audio_device():
    """Test StateManager audio device methods."""
    from app.state import StateManager
    from app.migrations import run_migrations
    import tempfile
    import os
    
    # Create temp database
    fd, db_path = tempfile.mkstemp(suffix='.db')
    os.close(fd)
    
    try:
        # Run migrations
        run_migrations(db_path)
        
        # Create state manager
        state = StateManager(db_path)
        
        # Test default value
        assert state.get_audio_device_index() == 0
        
        # Test setting device index
        state.set_audio_device_index(3, source="test", reason="Testing")
        assert state.get_audio_device_index() == 3
        
        # Test persistence
        state2 = StateManager(db_path)
        assert state2.get_audio_device_index() == 3
        
    finally:
        if os.path.exists(db_path):
            os.unlink(db_path)


@pytest.mark.asyncio
async def test_record_once_with_device():
    """Test record_once passes device_index correctly."""
    from app.audio_io import record_once
    import numpy as np
    
    # Mock the sync recording function
    with patch('app.audio_io._record_sync') as mock_record:
        mock_record.return_value = np.array([0.1, 0.2, 0.3], dtype=np.float32)
        
        audio = await record_once(
            seconds=1.0,
            device_index=5,
            sample_rate=16000,
            channels=1
        )
        
        # Verify _record_sync was called with correct parameters
        mock_record.assert_called_once_with(1.0, 5, 16000, 1)
        assert audio is not None
        assert len(audio) == 3
