# asr_worker.py
import asyncio
import logging
import time
import numpy as np
from faster_whisper import WhisperModel
from .echonet_client import post_text_event
from .audio_io import record_once
from .state import StateManager
from .registry import TargetRegistryRepository
from .settings import settings

log = logging.getLogger("echonet.asr")

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
    """
    # Short recording window to check for wake word
    audio = await record_once(
        seconds=2.0,
        device_index=device_index,
        sample_rate=settings.audio_sample_rate,
        channels=settings.audio_channels
    )
    
    if audio is None or len(audio) == 0:
        return
    
    # Transcribe to check for wake word
    text, confidence = await transcribe_audio(audio)
    
    if not text.strip():
        return
    
    # Check if text contains any target phrase
    phrase_map = registry.get_phrase_map()
    detected_target = None
    
    for phrase in phrase_map.keys():
        if phrase.lower() in text.lower():
            detected_target = phrase_map[phrase]
            log.info(f"Wake word detected: '{phrase}' -> target {detected_target}")
            break
    
    if detected_target:
        # Wake word detected! Send the transcription
        await post_text_event(
            source_id=settings.echonet_source_id,
            room=settings.echonet_room,
            ts=int(time.time()),
            text=text,
            confidence=confidence,
        )


async def _handle_active_mode(
    state_manager: StateManager,
    device_index: int,
    stop_event: asyncio.Event
) -> None:
    """
    Active mode: Continuous recording and transcription.
    Waits for silence before sending.
    """
    # Longer recording window for active listening
    audio = await record_once(
        seconds=3.0,
        device_index=device_index,
        sample_rate=settings.audio_sample_rate,
        channels=settings.audio_channels
    )
    
    if audio is None or len(audio) == 0:
        return
    
    # Transcribe
    text, confidence = await transcribe_audio(audio)
    
    if text.strip():
        # Send any non-empty transcription
        await post_text_event(
            source_id=settings.echonet_source_id,
            room=settings.echonet_room,
            ts=int(time.time()),
            text=text,
            confidence=confidence,
        )
