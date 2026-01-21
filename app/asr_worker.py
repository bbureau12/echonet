# asr_worker.py
import asyncio
import logging
import time
import os
from pathlib import Path
import numpy as np
from faster_whisper import WhisperModel
from .audio_io import record_until_silence, load_audio_file, stream_audio_file
from .state import StateManager
from .registry import TargetRegistryRepository
from .models import TextIn
from .settings import settings

log = logging.getLogger("echonet.asr")

# Will be set by main.py during startup
_text_handler = None

def set_text_handler(handler):
    """Set the text ingestion handler from main app."""
    global _text_handler
    _text_handler = handler

# Initialize Faster Whisper model (lazy-loaded)
_whisper_model = None

def get_whisper_model() -> WhisperModel:
    """Get or initialize the Faster Whisper model."""
    global _whisper_model
    if _whisper_model is None:
        log.info(f"Loading Faster Whisper model ({settings.whisper_model})...")
        # Options: tiny, base, small, medium, large-v2, large-v3
        # For faster performance on CPU, use "tiny" or "base"
        # For better accuracy, use "small" or "medium"
        _whisper_model = WhisperModel(
            settings.whisper_model,
            device=settings.whisper_device,
            compute_type=settings.whisper_compute_type
        )
        log.info(f"Faster Whisper model loaded successfully (device={settings.whisper_device})")
    return _whisper_model


async def transcribe_audio(audio: np.ndarray) -> tuple[str, float]:
    """
    Transcribe audio using Faster Whisper.
    
    Args:
        audio: NumPy array of audio samples (float32, -1.0 to 1.0)
        
    Returns:
        tuple of (transcribed_text, confidence)
    """
    if audio is None or len(audio) == 0:
        return "", 0.0
    
    # Run transcription in thread pool to avoid blocking the async loop
    loop = asyncio.get_event_loop()
    text, confidence = await loop.run_in_executor(
        None, 
        _transcribe_sync, 
        audio
    )
    
    return text, confidence


def _transcribe_sync(audio: np.ndarray) -> tuple[str, float]:
    """
    Synchronous transcription function (runs in executor).
    """
    try:
        model = get_whisper_model()
        
        # Faster Whisper expects float32 audio normalized to -1.0 to 1.0
        if audio.dtype != np.float32:
            audio = audio.astype(np.float32)
        
        # Transcribe with Faster Whisper
        segments, info = model.transcribe(
            audio,
            beam_size=5,
            language=None if settings.whisper_language == "auto" else settings.whisper_language,
            vad_filter=True,  # Voice Activity Detection
            vad_parameters=dict(
                min_silence_duration_ms=500,
                threshold=0.5
            )
        )
        
        # Combine all segments
        text_parts = []
        avg_confidence = 0.0
        segment_count = 0
        
        for segment in segments:
            text_parts.append(segment.text)
            # avg_logprob is negative, convert to 0-1 confidence
            # Typical range: -0.5 to -2.0, where closer to 0 is better
            segment_confidence = max(0.0, min(1.0, 1.0 + segment.avg_logprob))
            avg_confidence += segment_confidence
            segment_count += 1
        
        if segment_count > 0:
            avg_confidence /= segment_count
        
        text = " ".join(text_parts).strip()
        
        log.debug(f"Transcribed: '{text}' (confidence: {avg_confidence:.2f})")
        
        return text, avg_confidence
        
    except Exception as e:
        log.error(f"Transcription error: {e}")
        return "", 0.0


async def run_asr_worker(
    state_manager: StateManager,
    registry: TargetRegistryRepository,
    audio_devices: list,
    initial_device_index: int,
    stop_event: asyncio.Event
) -> None:
    """
    Main ASR worker loop supporting two modes:
    - trigger: Wake word detection, only transcribes after detecting a target phrase
    - active: Continuous recording and transcription
    
    Both modes wait for silence/end of speech before sending transcription.
    Monitors state changes via in-memory cache (not database polling).
    
    Args:
        state_manager: State manager for reading listen mode
        registry: Target registry for wake word phrase matching
        audio_devices: List of available audio devices
        initial_device_index: Initial device index to use
        stop_event: Event to signal worker shutdown
    """
    log.info("ASR worker starting...")
    
    # Check if in test mode
    if settings.test_mode:
        log.info("🧪 TEST MODE ENABLED - Using pre-recorded audio files")
        log.info(f"   Test audio directory: {settings.test_audio_dir}")
        await _run_test_mode(state_manager, registry, stop_event)
        return
    
    # Get initial state
    current_mode = state_manager.get_listen_mode()
    log.info(f"Initial mode: {current_mode}")
    
    # Track device index (updated from cache if multiple devices)
    device_index = initial_device_index
    
    while not stop_event.is_set():
        # Quick cache read (no database hit)
        mode = state_manager.get_listen_mode()
        
        # If mode changed, log it
        if mode != current_mode:
            log.info(f"Mode changed: {current_mode} -> {mode}")
            current_mode = mode
        
        # If multiple devices, check for device changes
        if len(audio_devices) > 1:
            cached_device = state_manager.get_audio_device_index()
            if cached_device != device_index:
                log.info(f"Audio device changed: {device_index} -> {cached_device}")
                device_index = cached_device
        
        if mode == "trigger":
            # Trigger mode: listen for wake words
            await _handle_trigger_mode(state_manager, registry, device_index, stop_event)
        else:  # active
            # Active mode: continuous recording
            await _handle_active_mode(state_manager, device_index, stop_event)
        
        # Small sleep to prevent tight loop
        await asyncio.sleep(0.05)
    
    log.info("ASR worker stopped")


async def _handle_trigger_mode(
    state_manager: StateManager,
    registry: TargetRegistryRepository,
    device_index: int,
    stop_event: asyncio.Event
) -> None:
    """
    Trigger mode: Listen for wake words, only transcribe when detected.
    Records until silence is detected.
    """
    # Record until silence (shorter timeout for trigger mode)
    audio = await record_until_silence(
        device_index=device_index,
        sample_rate=settings.audio_sample_rate,
        channels=settings.audio_channels,
        silence_duration=settings.audio_silence_duration,
        min_duration=settings.audio_min_duration,
        max_duration=10.0,  # Shorter max for trigger mode (wake words are brief)
        energy_threshold=settings.audio_energy_threshold,
        use_whisper_vad=settings.audio_use_whisper_vad
    )
    
    if audio is None or len(audio) == 0:
        return
    
    # Transcribe to check for wake word
    text, confidence = await transcribe_audio(audio)
    
    if not text.strip():
        return
    
    # Check if text contains any target phrase
    phrase_list = registry.phrase_map()
    detected_target = None
    
    for phrase, target_name in phrase_list:
        if phrase.lower() in text.lower():
            detected_target = target_name
            log.info(f"Wake word detected: '{phrase}' -> target {detected_target}")
            break
    
    if detected_target:
        # Wake word detected! Send to routing logic
        if _text_handler:
            text_input = TextIn(
                source_id=settings.echonet_source_id,
                room=settings.echonet_room,
                ts=int(time.time()),
                text=text,
                confidence=confidence
            )
            try:
                await _text_handler(text_input)
            except Exception as e:
                log.error(f"Failed to route text: {e}")
        else:
            log.warning("Text handler not set, cannot route wake word")


async def _handle_active_mode(
    state_manager: StateManager,
    device_index: int,
    stop_event: asyncio.Event
) -> None:
    """
    Active mode: Continuous recording and transcription.
    Records until silence is detected (person stops talking).
    """
    # Record until silence (full timeout for active conversation)
    audio = await record_until_silence(
        device_index=device_index,
        sample_rate=settings.audio_sample_rate,
        channels=settings.audio_channels,
        silence_duration=settings.audio_silence_duration,
        min_duration=settings.audio_min_duration,
        max_duration=settings.audio_max_duration,
        energy_threshold=settings.audio_energy_threshold,
        use_whisper_vad=settings.audio_use_whisper_vad
    )
    
    if audio is None or len(audio) == 0:
        return
    
    # Transcribe
    text, confidence = await transcribe_audio(audio)
    
    if text.strip():
        # Send any non-empty transcription to routing logic
        if _text_handler:
            text_input = TextIn(
                source_id=settings.echonet_source_id,
                room=settings.echonet_room,
                ts=int(time.time()),
                text=text,
                confidence=confidence
            )
            try:
                await _text_handler(text_input)
            except Exception as e:
                log.error(f"Failed to route text: {e}")
        else:
            log.warning("Text handler not set, cannot route text")


async def _run_test_mode(
    state_manager: StateManager,
    registry: TargetRegistryRepository,
    stop_event: asyncio.Event
) -> None:
    """
    Test mode: Process pre-recorded audio files instead of live microphone.
    
    Reads audio files from test_audio_dir and processes them in a loop,
    simulating the ASR worker behavior for testing.
    
    Expected directory structure:
        test_audio/
            trigger/           # Files with wake words
                hey_astraea.wav
                hello_echobell.wav
            active/            # Files to test active mode
                question1.wav
                answer1.wav
            silence.wav        # Empty/silent audio for timeout testing
    """
    test_dir = Path(settings.test_audio_dir)
    
    if not test_dir.exists():
        log.error(f"Test audio directory not found: {test_dir}")
        log.info(f"Create directory structure:")
        log.info(f"  {test_dir}/trigger/    - Audio files with wake words")
        log.info(f"  {test_dir}/active/     - Audio files for active mode")
        log.info(f"  {test_dir}/silence.wav - Silent audio for timeout testing")
        return
    
    # Find all WAV files in the test directory
    trigger_files = list((test_dir / "trigger").glob("*.wav")) if (test_dir / "trigger").exists() else []
    active_files = list((test_dir / "active").glob("*.wav")) if (test_dir / "active").exists() else []
    
    log.info(f"Found {len(trigger_files)} trigger test files, {len(active_files)} active test files")
    
    if not trigger_files and not active_files:
        log.warning("No test audio files found!")
        return
    
    cycle_count = 0
    
    while not stop_event.is_set():
        cycle_count += 1
        mode = state_manager.get_listen_mode()
        
        log.info(f"🧪 Test cycle #{cycle_count} - Mode: {mode}")
        
        # Select files based on mode
        test_files = trigger_files if mode == "trigger" else active_files
        
        if not test_files:
            log.warning(f"No test files for {mode} mode, skipping cycle")
            await asyncio.sleep(settings.test_loop_delay)
            continue
        
        # Process each test file
        for audio_file in test_files:
            if stop_event.is_set():
                break
            
            log.info(f"📁 Processing: {audio_file.name}")
            
            # Stream audio from file in chunks (simulating microphone input)
            audio_chunks = []
            chunk_count = 0
            
            async for chunk in stream_audio_file(str(audio_file), chunk_duration=0.1):
                if stop_event.is_set():
                    break
                audio_chunks.append(chunk)
                chunk_count += 1
            
            if not audio_chunks:
                log.warning(f"No audio chunks received from: {audio_file.name}")
                continue
            
            # Concatenate all chunks
            audio = np.concatenate(audio_chunks)
            log.info(f"   Received {chunk_count} chunks ({len(audio)/16000:.2f}s of audio)")
            
            # Transcribe
            start_time = time.time()
            text, confidence = await transcribe_audio(audio)
            transcribe_time = time.time() - start_time
            
            log.info(f"   Transcribed in {transcribe_time:.2f}s: '{text}' (confidence: {confidence:.2f})")
            
            if not text.strip():
                log.info(f"   Empty transcription, skipping routing")
                continue
            
            # Handle based on mode
            if mode == "trigger":
                # Check for wake word
                phrase_list = registry.phrase_map()
                detected_target = None
                
                for phrase, target_name in phrase_list:
                    if phrase.lower() in text.lower():
                        detected_target = target_name
                        log.info(f"   ✅ Wake word detected: '{phrase}' -> target {detected_target}")
                        break
                
                if not detected_target:
                    log.info(f"   ❌ No wake word detected")
                    continue
            else:
                log.info(f"   📤 Active mode - routing all text")
            
            # Send to routing logic
            if _text_handler:
                text_input = TextIn(
                    source_id="test_mode",
                    room=settings.echonet_room,
                    ts=int(time.time()),
                    text=text,
                    confidence=confidence
                )
                try:
                    decision = await _text_handler(text_input)
                    log.info(f"   Routed to: {decision.routed_to} (mode: {decision.mode})")
                except Exception as e:
                    log.error(f"   Failed to route: {e}")
            
            # Delay between files
            await asyncio.sleep(1.0)
        
        # Delay between cycles
        log.info(f"🧪 Test cycle #{cycle_count} complete, waiting {settings.test_loop_delay}s")
        await asyncio.sleep(settings.test_loop_delay)
    
    log.info("🧪 Test mode stopped")
