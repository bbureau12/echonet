"""
Integration tests for ASR worker modes.

These tests call the actual _handle_trigger_mode() and _handle_active_mode() functions
to verify end-to-end behavior including wake word routing logic.
"""
import pytest
import asyncio
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock
from app.asr_worker import _handle_trigger_mode, _handle_active_mode, set_text_handler
from app.audio_io import simulate_record_until_silence_from_file
from app.state import StateManager
from app.registry import TargetRegistryRepository
from app.models import TextIn


@pytest.fixture
def test_audio_dir_trigger():
    """Path to trigger mode test audio fixtures."""
    return Path(__file__).parent / "fixtures" / "awake_word"


@pytest.fixture
def test_audio_dir_active():
    """Path to active mode test audio fixtures."""
    return Path(__file__).parent / "fixtures" / "active_mode"


@pytest.fixture
def mock_state_manager(tmp_path):
    """State manager with temporary database."""
    db_path = tmp_path / "test_state.db"
    
    # Initialize with migrations
    from app.migrations import run_migrations
    run_migrations(str(db_path))
    
    state = StateManager(db_path=db_path)
    state.set_listen_mode("trigger", "test")
    return state


@pytest.fixture
def real_registry(tmp_path):
    """Real target registry with test database."""
    from app.registry import Target
    db_path = tmp_path / "test_registry.db"
    
    # Initialize with migrations
    from app.migrations import run_migrations
    run_migrations(str(db_path))
    
    registry = TargetRegistryRepository(db_path=db_path)
    
    # Add test target with "peter" wake word
    registry.upsert(Target(
        name="peter_target",
        base_url="http://localhost:9999",
        phrases=["peter", "hey peter"]
    ))
    
    return registry


@pytest.fixture
def mock_text_handler():
    """Mock text handler to capture routing calls."""
    handler = AsyncMock()
    set_text_handler(handler)
    yield handler
    # Clean up
    set_text_handler(None)


class TestTriggerModeIntegration:
    """Integration tests for trigger mode (_handle_trigger_mode)."""
    
    @pytest.mark.asyncio
    async def test_trigger_mode_with_wake_word_routes(
        self, 
        test_audio_dir_trigger,
        mock_state_manager,
        real_registry,
        mock_text_handler,
        monkeypatch
    ):
        """
        INTEGRATION TEST: Trigger mode with wake word should route to handler.
        
        This test:
        1. Calls actual _handle_trigger_mode() function
        2. Uses real registry with "peter" wake word
        3. Mocks record_until_silence to return pre-recorded audio
        4. Verifies text_handler is called with correct text
        """
        audio_files = list(test_audio_dir_trigger.glob("*.wav"))
        if not audio_files:
            pytest.skip("No test audio files found")
        
        # Find a file with wake word "peter" and "coffee"
        test_file = None
        for f in audio_files:
            if "0630" in f.name or "0631" in f.name or "0635" in f.name:
                test_file = f
                break
        
        if not test_file:
            test_file = audio_files[0]
        
        print(f"\n🧪 Testing trigger mode integration with: {test_file.name}")
        
        # Mock record_until_silence to return simulated capture
        async def mock_record(*args, **kwargs):
            return await simulate_record_until_silence_from_file(
                str(test_file),
                silence_duration=1.0,
                min_duration=0.5,
                max_duration=30.0,
                energy_threshold=0.01,
                use_whisper_vad=True
            )
        
        from app import asr_worker
        monkeypatch.setattr(asr_worker, 'record_until_silence', mock_record)
        
        # Call actual trigger mode handler
        stop_event = asyncio.Event()
        await _handle_trigger_mode(
            state_manager=mock_state_manager,
            registry=real_registry,
            device_index=0,
            stop_event=stop_event
        )
        
        # Verify handler was called
        assert mock_text_handler.called, "Text handler should be called when wake word detected"
        
        # Get the call arguments
        call_args = mock_text_handler.call_args[0][0]
        assert isinstance(call_args, TextIn), "Handler should receive TextIn object"
        
        # Verify wake word is in the text
        text_lower = call_args.text.lower()
        assert "peter" in text_lower, f"Wake word 'peter' should be in routed text: '{call_args.text}'"
        assert "coffee" in text_lower or "cup" in text_lower, \
            f"Coffee request should be in routed text: '{call_args.text}'"
        
        print(f"✅ Routed text: '{call_args.text}'")
        print(f"✅ Confidence: {call_args.confidence:.2f}")
        print(f"✅ Integration test PASSED: Trigger mode correctly detected wake word and routed")
    
    
    @pytest.mark.asyncio
    async def test_trigger_mode_without_wake_word_ignores(
        self,
        test_audio_dir_trigger,
        mock_state_manager,
        real_registry,
        mock_text_handler,
        monkeypatch
    ):
        """
        INTEGRATION TEST: Trigger mode without wake word should NOT route.
        
        This test:
        1. Uses audio file with NO wake word (just "cake" phrase)
        2. Verifies text_handler is NOT called
        """
        audio_files = list(test_audio_dir_trigger.glob("*.wav"))
        if not audio_files:
            pytest.skip("No test audio files found")
        
        # Find file with cake but no wake word (260121_0638.wav starts with cake)
        test_file = None
        for f in audio_files:
            if "0638" in f.name:
                test_file = f
                break
        
        if not test_file:
            pytest.skip("No test file with non-wake-word phrase found")
        
        print(f"\n🧪 Testing trigger mode integration (no wake word): {test_file.name}")
        
        # Mock record_until_silence to return simulated capture
        async def mock_record(*args, **kwargs):
            return await simulate_record_until_silence_from_file(
                str(test_file),
                silence_duration=1.0,
                min_duration=0.5,
                max_duration=30.0,
                energy_threshold=0.01,
                use_whisper_vad=True
            )
        
        from app import asr_worker
        monkeypatch.setattr(asr_worker, 'record_until_silence', mock_record)
        
        # Reset mock to ensure clean state
        mock_text_handler.reset_mock()
        
        # Call actual trigger mode handler
        stop_event = asyncio.Event()
        await _handle_trigger_mode(
            state_manager=mock_state_manager,
            registry=real_registry,
            device_index=0,
            stop_event=stop_event
        )
        
        # Verify handler was NOT called (no wake word)
        assert not mock_text_handler.called, \
            "Text handler should NOT be called when no wake word detected"
        
        print(f"✅ Integration test PASSED: Trigger mode correctly ignored non-wake-word phrase")


class TestActiveModeIntegration:
    """Integration tests for active mode (_handle_active_mode)."""
    
    @pytest.mark.asyncio
    async def test_active_mode_routes_all_text(
        self,
        test_audio_dir_active,
        mock_state_manager,
        mock_text_handler,
        monkeypatch
    ):
        """
        INTEGRATION TEST: Active mode should route ALL captured text.
        
        This test:
        1. Calls actual _handle_active_mode() function
        2. Uses audio without wake word
        3. Verifies text_handler is called (no wake word check)
        """
        audio_files = list(test_audio_dir_active.glob("*.wav"))
        if not audio_files:
            pytest.skip("No test audio files found")
        
        test_file = audio_files[0]
        print(f"\n🧪 Testing active mode integration with: {test_file.name}")
        
        # Mock record_until_silence to return simulated capture
        async def mock_record(*args, **kwargs):
            return await simulate_record_until_silence_from_file(
                str(test_file),
                silence_duration=1.0,
                min_duration=0.5,
                max_duration=30.0,
                energy_threshold=0.01,
                use_whisper_vad=True
            )
        
        from app import asr_worker
        monkeypatch.setattr(asr_worker, 'record_until_silence', mock_record)
        
        # Call actual active mode handler
        stop_event = asyncio.Event()
        await _handle_active_mode(
            state_manager=mock_state_manager,
            device_index=0,
            stop_event=stop_event
        )
        
        # Verify handler was called (active mode routes all text)
        assert mock_text_handler.called, \
            "Text handler should be called in active mode (no wake word check)"
        
        # Get the call arguments
        call_args = mock_text_handler.call_args[0][0]
        assert isinstance(call_args, TextIn), "Handler should receive TextIn object"
        
        # Verify text is not empty
        assert len(call_args.text.strip()) > 0, "Routed text should not be empty"
        
        # Active mode doesn't check for wake words - should route whatever was captured
        text_lower = call_args.text.lower()
        assert "dangerous" in text_lower or "hold" in text_lower, \
            f"Expected phrase should be in routed text: '{call_args.text}'"
        
        print(f"✅ Routed text: '{call_args.text}'")
        print(f"✅ Confidence: {call_args.confidence:.2f}")
        print(f"✅ Integration test PASSED: Active mode correctly routed all text (no wake word check)")
        
        # Verify mode was reset back to trigger
        final_mode = mock_state_manager.get_listen_mode()
        assert final_mode == "trigger", \
            f"Active mode should reset to trigger after completion, but got: {final_mode}"
        print(f"✅ Mode correctly reset to trigger after active mode completion")
    
    
    @pytest.mark.asyncio
    async def test_active_mode_resets_on_timeout(
        self,
        mock_state_manager,
        mock_text_handler,
        monkeypatch
    ):
        """
        INTEGRATION TEST: Active mode should reset to trigger on timeout (no audio).
        
        This test:
        1. Calls _handle_active_mode() with no audio (timeout)
        2. Verifies mode is reset to trigger
        3. Verifies text_handler is NOT called
        """
        print(f"\n🧪 Testing active mode timeout behavior")
        
        # Mock record_until_silence to return None (timeout)
        async def mock_record(*args, **kwargs):
            return None  # Simulate timeout with no audio
        
        from app import asr_worker
        monkeypatch.setattr(asr_worker, 'record_until_silence', mock_record)
        
        # Call actual active mode handler
        stop_event = asyncio.Event()
        await _handle_active_mode(
            state_manager=mock_state_manager,
            device_index=0,
            stop_event=stop_event
        )
        
        # Verify handler was NOT called (no audio captured)
        assert not mock_text_handler.called, \
            "Text handler should NOT be called when no audio captured"
        
        # Verify mode was reset back to trigger
        final_mode = mock_state_manager.get_listen_mode()
        assert final_mode == "trigger", \
            f"Active mode should reset to trigger after timeout, but got: {final_mode}"
        
        print(f"✅ Integration test PASSED: Active mode correctly reset to trigger on timeout")
