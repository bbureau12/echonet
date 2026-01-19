# asr_worker.py
import asyncio
import logging
import time
import numpy as np
from faster_whisper import WhisperModel
from .echonet_client import post_text_event
from .audio_io import record_once
from .state import RuntimeState
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


async def run_asr_worker(st: RuntimeState) -> None:
    while not st.stop_event.is_set():
        # snapshot state
        async with st.lock:
            enabled = st.enabled
            room = st.room
            source_id = st.source_id

        if not enabled:
            await asyncio.sleep(0.2)
            continue

        # v0.1: push-to-talk or fixed recording windows
        audio = await record_once(seconds=3.0)   # later: VAD/wakeword

        # heavy work: run whisper in executor so we don't block the loop
        text, conf = await transcribe_audio(audio)

        if text.strip():
            await post_text_event(
                source_id=source_id,
                room=room,
                ts=int(time.time()),
                text=text,
                confidence=conf,
            )

        await asyncio.sleep(0.05)
