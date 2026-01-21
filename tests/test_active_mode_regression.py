"""
COMPONENT/REGRESSION TESTS for active mode recording.

These tests verify active mode components work correctly:
- VAD captures audio and stops at silence gaps
- Transcription works in active mode
- No wake word filtering (all text is captured)

What these tests do NOT cover:
- Actual _handle_active_mode() function call (see test_integration_modes.py)
- End-to-end flow through active mode handler

Test approach:
1. Stream WAV file in chunks (0.5s) to simulate real-time audio
2. Apply Whisper VAD to detect silence and stop recording
3. Transcribe captured audio
4. Verify expected phrase is present (no wake word check required)
"""
import pytest
import asyncio
from pathlib import Path
from app.asr_worker import transcribe_audio
from app.audio_io import load_audio_file, simulate_record_until_silence_from_file


@pytest.fixture
def test_audio_dir():
    """Path to test audio fixtures."""
    return Path(__file__).parent / "fixtures" / "active_mode"


class TestActiveModeRecording:
    """Test active mode continuous recording with real audio files."""
    
    @pytest.mark.asyncio
    async def test_realistic_active_mode_vad(self, test_audio_dir):
        """
        Test ACTIVE MODE with realistic VAD simulation.
        
        In active mode:
        - No wake word detection
        - Records continuously until silence detected
        - Routes ALL captured text
        
        Expected behavior:
        - Should capture first phrase completely
        - Should stop at silence gap (>1s)
        - Should NOT capture phrase after the gap
        """
        audio_files = sorted(list(test_audio_dir.glob("*.wav")))
        
        if not audio_files:
            pytest.skip("No test audio files found in tests/fixtures/active_mode/")
        
        print(f"\n{'='*70}")
        print(f"🎯 ACTIVE MODE - REALISTIC VAD SIMULATION TEST")
        print(f"{'='*70}")
        print(f"\nTesting {len(audio_files)} audio file(s)...")
        
        all_results = []
        
        for audio_file in audio_files:
            print(f"\n{'─'*70}")
            print(f"📁 File: {audio_file.name}")
            print(f"{'─'*70}")
            
            # First: show what the FULL file contains
            print(f"\n1️⃣  Loading FULL audio file (no VAD)...")
            full_audio = await load_audio_file(str(audio_file))
            full_text, full_conf = await transcribe_audio(full_audio)
            print(f"   Full transcription: '{full_text}'")
            
            # Check for expected phrases
            has_first_phrase = 'hold on tight' in full_text.lower() and 'dangerous' in full_text.lower()
            has_second_phrase = 'make ends meet' in full_text.lower()
            
            print(f"   Contains first phrase: {has_first_phrase}")
            print(f"   Contains second phrase (after gap): {has_second_phrase}")
            
            # Second: simulate actual record_until_silence behavior
            print(f"\n2️⃣  Simulating ACTIVE MODE recording with Whisper VAD...")
            print(f"   - No wake word detection (active mode)")
            print(f"   - Chunk size: 0.5s (same as production)")
            print(f"   - Silence duration: 1.0s (stops after 1s of no speech)")
            print(f"   - Using Whisper VAD")
            
            captured_audio = await simulate_record_until_silence_from_file(
                str(audio_file),
                silence_duration=1.0,
                min_duration=0.5,
                max_duration=30.0,
                energy_threshold=0.01,
                use_whisper_vad=True
            )
            
            if captured_audio is None:
                print(f"   ❌ Simulation failed to capture audio")
                all_results.append({
                    'file': audio_file.name,
                    'status': 'FAILED',
                    'reason': 'No audio captured'
                })
                continue
            
            # Third: transcribe only what was captured
            print(f"\n3️⃣  Transcribing captured audio...")
            captured_text, captured_conf = await transcribe_audio(captured_audio)
            print(f"   Captured transcription: '{captured_text}'")
            
            # Fourth: analyze results
            print(f"\n4️⃣  Analysis:")
            captured_lower = captured_text.lower()
            captured_first = 'hold on tight' in captured_lower and 'dangerous' in captured_lower
            captured_second = 'make ends meet' in captured_lower
            
            print(f"   ✓ First phrase captured: {captured_first}")
            print(f"   ✓ Second phrase captured: {captured_second}")
            
            # Store results
            result = {
                'file': audio_file.name,
                'has_first': captured_first,
                'has_second': captured_second,
                'captured_text': captured_text,
                'full_text': full_text
            }
            all_results.append(result)
            
            # Determine test outcome
            if captured_first and not captured_second:
                # Perfect: first phrase captured, stopped at gap
                print(f"\n   ✅ SUCCESS: Captured first phrase, stopped at silence gap!")
                print(f"   In active mode, this would be routed (no wake word check).")
                result['status'] = 'PASSED'
            elif captured_first and captured_second:
                # Bad: both phrases captured (gap too short)
                print(f"\n   ❌ FAILED: Both phrases captured!")
                print(f"   Gap was too short or VAD didn't detect the silence.")
                result['status'] = 'FAILED'
            elif not captured_first:
                # Bad: first phrase not captured
                print(f"\n   ❌ FAILED: First phrase not captured!")
                result['status'] = 'FAILED'
            else:
                # Unexpected
                print(f"\n   ⚠️  WARNING: Unexpected result")
                result['status'] = 'WARNING'
        
        # Summary
        print(f"\n{'='*70}")
        print(f"📊 SUMMARY")
        print(f"{'='*70}")
        passed = sum(1 for r in all_results if r.get('status') == 'PASSED')
        failed = sum(1 for r in all_results if r.get('status') == 'FAILED')
        warnings = sum(1 for r in all_results if r.get('status') == 'WARNING')
        print(f"Total files: {len(all_results)}")
        print(f"✅ Passed: {passed}")
        print(f"❌ Failed: {failed}")
        if warnings:
            print(f"⚠️  Warnings: {warnings}")
        
        for result in all_results:
            status_icon = '✅' if result.get('status') == 'PASSED' else ('❌' if result.get('status') == 'FAILED' else '⚠️ ')
            print(f"\n{status_icon} {result['file']}")
            if 'captured_text' in result:
                print(f"   Captured: '{result['captured_text']}'")
                if result.get('status') == 'PASSED':
                    print(f"   → Would route in active mode (all text routed)")
        
        print(f"{'='*70}\n")
        
        # Assert: all files should pass (first phrase only, no second phrase)
        failures = [r for r in all_results if r.get('status') == 'FAILED']
        assert len(failures) == 0, \
            f"{len(failures)} file(s) failed: either didn't capture first phrase or captured both phrases"
    
    
    @pytest.mark.asyncio
    async def test_active_mode_routes_all_text(self, test_audio_dir):
        """
        Test that active mode routes ALL captured text (no wake word filtering).
        
        Expected behavior:
        - Unlike trigger mode, no wake word check
        - All captured text should be routed
        - This is the key difference from trigger mode
        """
        audio_files = list(test_audio_dir.glob("*.wav"))
        
        if not audio_files:
            pytest.skip("No test audio files found in tests/fixtures/active_mode/")
        
        audio_file = audio_files[0]
        
        # Simulate capture
        captured_audio = await simulate_record_until_silence_from_file(
            str(audio_file),
            silence_duration=1.0,
            min_duration=0.5,
            max_duration=30.0,
            energy_threshold=0.01,
            use_whisper_vad=True
        )
        
        assert captured_audio is not None, "Failed to capture audio"
        
        # Transcribe
        text, confidence = await transcribe_audio(captured_audio)
        
        # In active mode, ANY text would be routed (no wake word check)
        # Just verify we got some text
        assert len(text.strip()) > 0, "No text captured"
        
        print(f"\n✅ Active mode test:")
        print(f"   Captured: '{text}'")
        print(f"   In active mode: Would route ALL captured text")
        print(f"   In trigger mode: Would check for wake word first")
