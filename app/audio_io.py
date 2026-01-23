# audio_io.py
"""Audio input/output handling with device management."""

import asyncio
import logging
from dataclasses import dataclass
from typing import Optional
from collections import deque
import numpy as np
import sounddevice as sd

log = logging.getLogger("echonet.audio")


class RingBuffer:
    """
    Ring buffer for storing recent audio chunks (pre-roll buffering).
    
    Maintains a fixed-duration sliding window of recent audio data
    to capture audio before a trigger event (e.g., button press).
    """
    
    def __init__(self, duration_seconds: float, sample_rate: int = 16000, channels: int = 1):
        """
        Initialize ring buffer.
        
        Args:
            duration_seconds: How much audio history to keep
            sample_rate: Audio sample rate
            channels: Number of audio channels
        """
        self.duration_seconds = duration_seconds
        self.sample_rate = sample_rate
        self.channels = channels
        self.max_chunks = int(duration_seconds / 0.1) + 1  # Assuming ~0.1s chunks
        self._buffer: deque = deque(maxlen=self.max_chunks)
        self._total_duration = 0.0
    
    def add_chunk(self, audio_chunk: np.ndarray) -> None:
        """Add audio chunk to ring buffer (oldest chunks are automatically dropped)."""
        chunk_duration = len(audio_chunk) / self.sample_rate
        self._buffer.append((audio_chunk, chunk_duration))
        self._total_duration = sum(duration for _, duration in self._buffer)
    
    def get_buffered_audio(self) -> Optional[np.ndarray]:
        """
        Get all buffered audio as a single numpy array.
        
        Returns:
            Concatenated audio data or None if buffer is empty
        """
        if not self._buffer:
            return None
        
        chunks = [chunk for chunk, _ in self._buffer]
        return np.concatenate(chunks)
    
    def get_duration(self) -> float:
        """Get total duration of buffered audio in seconds."""
        return self._total_duration
    
    def clear(self) -> None:
        """Clear the ring buffer."""
        self._buffer.clear()
        self._total_duration = 0.0
    
    def is_full(self) -> bool:
        """Check if buffer has reached target duration."""
        return self._total_duration >= self.duration_seconds


@dataclass
class AudioDevice:
    """Represents an audio input device."""
    index: int
    name: str
    channels: int
    sample_rate: float
    is_default: bool


def list_audio_devices() -> list[AudioDevice]:
    """
    Get a list of all available audio input devices.
    
    Returns:
        List of AudioDevice objects with device information
    """
    devices = []
    default_input = sd.default.device[0]  # (input, output)
    
    for idx, device in enumerate(sd.query_devices()):
        # Only include devices with input channels
        if device['max_input_channels'] > 0:
            devices.append(AudioDevice(
                index=idx,
                name=device['name'],
                channels=device['max_input_channels'],
                sample_rate=device['default_samplerate'],
                is_default=(idx == default_input)
            ))
    
    return devices


def get_default_device() -> Optional[AudioDevice]:
    """
    Get the system's default audio input device.
    
    Returns:
        AudioDevice for the default input, or None if none available
    """
    try:
        default_idx = sd.default.device[0]
        device_info = sd.query_devices(default_idx)
        
        if device_info['max_input_channels'] > 0:
            return AudioDevice(
                index=default_idx,
                name=device_info['name'],
                channels=device_info['max_input_channels'],
                sample_rate=device_info['default_samplerate'],
                is_default=True
            )
    except Exception as e:
        log.error(f"Failed to get default audio device: {e}")
    
    return None


async def record_once(
    seconds: float,
    device_index: Optional[int] = None,
    sample_rate: int = 16000,
    channels: int = 1
) -> Optional[np.ndarray]:
    """
    Record audio from the specified device for a fixed duration.
    
    Args:
        seconds: Duration to record in seconds
        device_index: Audio device index (None = use system default)
        sample_rate: Sample rate in Hz (16kHz is good for speech)
        channels: Number of audio channels (1 = mono, 2 = stereo)
        
    Returns:
        NumPy array of audio samples (float32, -1.0 to 1.0) or None on error
    """
    try:
        # Record audio synchronously (sounddevice blocks)
        # Run in thread pool to avoid blocking async loop
        loop = asyncio.get_event_loop()
        audio = await loop.run_in_executor(
            None,
            _record_sync,
            seconds,
            device_index,
            sample_rate,
            channels
        )
        return audio
        
    except Exception as e:
        log.error(f"Audio recording failed: {e}")
        return None


def _record_sync(
    seconds: float,
    device_index: Optional[int],
    sample_rate: int,
    channels: int
) -> np.ndarray:
    """Synchronous recording helper (runs in thread pool)."""
    log.debug(f"Recording {seconds}s from device {device_index}...")
    
    recording = sd.rec(
        int(seconds * sample_rate),
        samplerate=sample_rate,
        channels=channels,
        device=device_index,
        dtype='float32'
    )
    sd.wait()  # Wait for recording to complete
    
    # Convert to mono if stereo
    if channels > 1:
        recording = np.mean(recording, axis=1)
    
    return recording.flatten()


async def stream_audio_file(file_path: str, chunk_duration: float = 0.1):
    """
    Stream audio from a file in chunks, simulating microphone input.
    
    Args:
        file_path: Path to audio file (WAV, MP3, FLAC, etc.)
        chunk_duration: Duration of each chunk in seconds (default 0.1s = 100ms)
        
    Yields:
        NumPy arrays of audio samples (float32, -1.0 to 1.0)
    """
    try:
        import soundfile as sf
        
        # Open file
        with sf.SoundFile(file_path) as audio_file:
            sample_rate = audio_file.samplerate
            channels = audio_file.channels
            
            # Calculate chunk size in samples
            chunk_size = int(chunk_duration * sample_rate)
            
            log.info(f"Streaming audio file: {file_path} ({sample_rate}Hz, {channels}ch)")
            
            while True:
                # Read chunk
                chunk = audio_file.read(chunk_size, dtype='float32')
                
                if len(chunk) == 0:
                    break
                
                # Convert to mono if stereo
                if channels > 1 and len(chunk.shape) > 1:
                    chunk = np.mean(chunk, axis=1)
                
                # Resample if needed (basic resampling)
                if sample_rate != 16000:
                    ratio = 16000 / sample_rate
                    new_length = int(len(chunk) * ratio)
                    chunk = np.interp(
                        np.linspace(0, len(chunk), new_length),
                        np.arange(len(chunk)),
                        chunk
                    )
                
                # Simulate real-time delay
                await asyncio.sleep(chunk_duration)
                
                yield chunk.flatten()
                
    except Exception as e:
        log.error(f"Failed to stream audio file {file_path}: {e}")
        return


async def simulate_record_until_silence_from_file(
    file_path: str,
    silence_duration: float = 1.0,
    min_duration: float = 0.5,
    max_duration: float = 30.0,
    energy_threshold: float = 0.01,
    use_whisper_vad: bool = True
) -> Optional[np.ndarray]:
    """
    Simulate record_until_silence() by streaming a WAV file and applying the same VAD logic.
    This allows testing the actual recording process without a microphone.
    
    Args:
        file_path: Path to audio file (WAV, MP3, FLAC, etc.)
        silence_duration: Seconds of silence before stopping (default: 1.0s)
        min_duration: Minimum recording duration in seconds (default: 0.5s)
        max_duration: Maximum recording duration in seconds (default: 30s)
        energy_threshold: Audio energy threshold for initial sound detection (0.0-1.0)
        use_whisper_vad: Use Faster Whisper's VAD for speech detection (default: True)
        
    Returns:
        NumPy array of audio samples that would have been captured, or None on error
    """
    try:
        import soundfile as sf
        
        loop = asyncio.get_event_loop()
        audio = await loop.run_in_executor(
            None,
            _simulate_record_until_silence_from_file_sync,
            file_path,
            silence_duration,
            min_duration,
            max_duration,
            energy_threshold,
            use_whisper_vad
        )
        return audio
        
    except Exception as e:
        log.error(f"Failed to simulate recording from file {file_path}: {e}")
        return None


def _simulate_record_until_silence_from_file_sync(
    file_path: str,
    silence_duration: float,
    min_duration: float,
    max_duration: float,
    energy_threshold: float,
    use_whisper_vad: bool
) -> Optional[np.ndarray]:
    """Synchronous simulation of VAD recording from file (runs in thread pool)."""
    import soundfile as sf
    
    # Use same chunk size as real recording
    chunk_duration = 0.5 if use_whisper_vad else 0.1
    silence_chunks_needed = int(silence_duration / chunk_duration)
    
    chunks = []
    silence_counter = 0
    speech_detected = False
    total_duration = 0.0
    
    # Load Whisper for VAD if needed
    whisper_model = None
    if use_whisper_vad:
        try:
            from faster_whisper import WhisperModel
            log.debug("Loading Whisper model for VAD simulation...")
            whisper_model = WhisperModel("tiny", device="cpu", compute_type="int8")
        except Exception as e:
            log.warning(f"Failed to load Whisper for VAD, falling back to energy-based: {e}")
            use_whisper_vad = False
    
    vad_method = "Whisper VAD" if use_whisper_vad else "energy-based"
    log.info(f"Simulating record_until_silence from file ({vad_method})...")
    
    try:
        with sf.SoundFile(file_path) as audio_file:
            sample_rate = audio_file.samplerate
            channels = audio_file.channels
            chunk_samples = int(chunk_duration * sample_rate)
            
            chunk_counter = 0
            
            while total_duration < max_duration:
                # Read next chunk
                chunk = audio_file.read(chunk_samples, dtype='float32')
                
                if len(chunk) == 0:
                    log.debug(f"End of file reached at {total_duration:.1f}s")
                    break
                
                # Convert to mono if needed
                if channels > 1 and len(chunk.shape) > 1:
                    mono_chunk = np.mean(chunk, axis=1)
                else:
                    mono_chunk = chunk.flatten() if len(chunk.shape) > 1 else chunk
                
                # Resample to 16kHz if needed
                if sample_rate != 16000:
                    ratio = 16000 / sample_rate
                    new_length = int(len(mono_chunk) * ratio)
                    mono_chunk = np.interp(
                        np.linspace(0, len(mono_chunk), new_length),
                        np.arange(len(mono_chunk)),
                        mono_chunk
                    )
                
                # Ensure float32 dtype for Whisper VAD
                mono_chunk = mono_chunk.astype(np.float32)
                
                chunks.append(mono_chunk)
                chunk_counter += 1
                chunk_actual_duration = len(mono_chunk) / 16000
                total_duration += chunk_actual_duration
                
                # Energy check
                energy = np.sqrt(np.mean(mono_chunk ** 2))
                is_speech = False
                
                if energy < energy_threshold:
                    is_speech = False
                elif use_whisper_vad and whisper_model:
                    # Verify with Whisper VAD
                    try:
                        segments, info = whisper_model.transcribe(
                            mono_chunk,
                            vad_filter=True,
                            vad_parameters=dict(
                                min_silence_duration_ms=300,
                                threshold=0.5
                            )
                        )
                        segment_list = list(segments)
                        is_speech = len(segment_list) > 0
                        
                        if is_speech:
                            speech_detected = True
                            log.debug(f"Chunk {chunk_counter} ({total_duration:.1f}s): Speech detected (energy={energy:.4f})")
                        else:
                            log.debug(f"Chunk {chunk_counter} ({total_duration:.1f}s): No speech (energy={energy:.4f})")
                            
                    except Exception as e:
                        log.warning(f"Whisper VAD error: {e}")
                        is_speech = energy >= energy_threshold
                else:
                    is_speech = energy >= energy_threshold
                
                # Update silence counter
                if is_speech:
                    silence_counter = 0
                else:
                    silence_counter += 1
                
                # Stop conditions (same as real record_until_silence)
                if total_duration >= min_duration and speech_detected:
                    if silence_counter >= silence_chunks_needed:
                        log.info(f"✂️  Would stop recording: {silence_duration}s of no speech after {total_duration:.1f}s")
                        break
        
        if not chunks:
            return None
        
        # Concatenate all captured chunks
        recording = np.concatenate(chunks)
        log.info(f"📼 Simulated capture: {len(recording)/16000:.1f}s of audio ({chunk_counter} chunks)")
        
        return recording.flatten()
        
    except Exception as e:
        log.error(f"Simulation error: {e}")
        return None


async def load_audio_file(file_path: str) -> Optional[np.ndarray]:
    """
    Load entire audio file for testing (non-streaming).
    
    Args:
        file_path: Path to audio file (WAV, MP3, FLAC, etc.)
        
    Returns:
        NumPy array of audio samples (float32, -1.0 to 1.0) or None on error
    """
    try:
        import soundfile as sf
        
        loop = asyncio.get_event_loop()
        audio = await loop.run_in_executor(
            None,
            _load_audio_file_sync,
            file_path
        )
        return audio
        
    except Exception as e:
        log.error(f"Failed to load audio file {file_path}: {e}")
        return None


def _load_audio_file_sync(file_path: str) -> Optional[np.ndarray]:
    """Synchronous audio file loading (runs in thread pool)."""
    import soundfile as sf
    
    try:
        # Load audio file
        audio_data, sample_rate = sf.read(file_path, dtype='float32')
        
        # Convert to mono if stereo
        if len(audio_data.shape) > 1:
            audio_data = np.mean(audio_data, axis=1)
        
        # Resample if needed (basic resampling - for better quality use librosa)
        if sample_rate != 16000:
            log.warning(f"Audio file is {sample_rate}Hz, expected 16kHz. Quality may be reduced.")
            # Simple decimation/interpolation
            ratio = 16000 / sample_rate
            new_length = int(len(audio_data) * ratio)
            audio_data = np.interp(
                np.linspace(0, len(audio_data), new_length),
                np.arange(len(audio_data)),
                audio_data
            )
        
        return audio_data.astype(np.float32)
        
    except Exception as e:
        log.error(f"Error loading audio file: {e}")
        return None


async def record_until_silence(
    device_index: Optional[int] = None,
    sample_rate: int = 16000,
    channels: int = 1,
    silence_duration: float = 1.0,
    min_duration: float = 0.5,
    max_duration: float = 30.0,
    energy_threshold: float = 0.01,
    use_whisper_vad: bool = True,
    preroll_buffer: Optional[RingBuffer] = None
) -> Optional[np.ndarray]:
    """
    Record audio continuously until silence is detected.
    
    Args:
        device_index: Audio device index (None = use system default)
        sample_rate: Sample rate in Hz (16kHz is good for speech)
        channels: Number of audio channels (1 = mono, 2 = stereo)
        silence_duration: Seconds of silence before stopping (default: 1.0s)
        min_duration: Minimum recording duration in seconds (default: 0.5s)
        max_duration: Maximum recording duration in seconds (default: 30s)
        energy_threshold: Audio energy threshold for initial sound detection (0.0-1.0)
        use_whisper_vad: Use Faster Whisper's VAD for speech detection (default: True)
        preroll_buffer: Optional RingBuffer to prepend buffered audio before recording
        
    Returns:
        NumPy array of audio samples (float32, -1.0 to 1.0) or None on error
        
    How it works with Whisper VAD:
        - Records in chunks (e.g., 0.5s at a time)
        - Uses energy threshold for initial sound detection (fast)
        - Uses Faster Whisper VAD to verify actual speech (accurate)
        - Stops when no speech detected for silence_duration seconds
        - Has safety timeout at max_duration
        
    Pre-roll buffering:
        - If preroll_buffer is provided, prepends buffered audio before the recording
        - Useful for capturing audio before a trigger event (e.g., doorbell button press)
    """
    try:
        loop = asyncio.get_event_loop()
        audio = await loop.run_in_executor(
            None,
            _record_until_silence_sync,
            device_index,
            sample_rate,
            channels,
            silence_duration,
            min_duration,
            max_duration,
            energy_threshold,
            use_whisper_vad,
            preroll_buffer
        )
        return audio
        
    except Exception as e:
        log.error(f"Audio recording failed: {e}")
        return None


def _record_until_silence_sync(
    device_index: Optional[int],
    sample_rate: int,
    channels: int,
    silence_duration: float,
    min_duration: float,
    max_duration: float,
    energy_threshold: float,
    use_whisper_vad: bool,
    preroll_buffer: Optional[RingBuffer] = None
) -> Optional[np.ndarray]:
    """Synchronous streaming VAD recording with Whisper speech detection (runs in thread pool)."""
    import queue
    
    # Use larger chunks for Whisper VAD (needs enough audio to analyze)
    # 0.5s is a good balance between responsiveness and accuracy
    chunk_duration = 0.5 if use_whisper_vad else 0.1
    chunk_samples = int(chunk_duration * sample_rate)
    silence_chunks_needed = int(silence_duration / chunk_duration)
    max_chunks = int(max_duration / chunk_duration)
    min_chunks = int(min_duration / chunk_duration)
    
    audio_queue = queue.Queue()
    chunks = []
    
    # If pre-roll buffer provided, prepend buffered audio
    preroll_audio = None
    if preroll_buffer is not None:
        preroll_audio = preroll_buffer.get_buffered_audio()
        if preroll_audio is not None:
            preroll_duration = preroll_buffer.get_duration()
            log.info(f"Prepending {preroll_duration:.1f}s of pre-roll audio to recording")
    
    silence_counter = 0
    chunk_counter = 0
    speech_detected = False  # Track if we've detected any speech yet
    
    # Import Whisper VAD if needed
    whisper_model = None
    if use_whisper_vad:
        try:
            from faster_whisper import WhisperModel
            # Load a tiny model just for VAD (much faster than transcription)
            # We only need VAD, not full transcription here
            log.debug("Loading Whisper model for VAD...")
            whisper_model = WhisperModel("tiny", device="cpu", compute_type="int8")
        except Exception as e:
            log.warning(f"Failed to load Whisper for VAD, falling back to energy-based: {e}")
            use_whisper_vad = False
    
    def audio_callback(indata, frames, time_info, status):
        """Called by sounddevice for each audio chunk."""
        if status:
            log.warning(f"Audio callback status: {status}")
        # Copy to avoid issues with buffer reuse
        audio_queue.put(indata.copy())
    
    vad_method = "Whisper VAD" if use_whisper_vad else "energy-based"
    log.debug(f"Starting streaming recording ({vad_method}, silence={silence_duration}s, max={max_duration}s)...")
    
    try:
        # Start streaming
        with sd.InputStream(
            samplerate=sample_rate,
            channels=channels,
            device=device_index,
            dtype='float32',
            blocksize=chunk_samples,
            callback=audio_callback
        ):
            while chunk_counter < max_chunks:
                try:
                    # Get next chunk (with timeout)
                    chunk = audio_queue.get(timeout=1.0)
                    chunks.append(chunk)
                    chunk_counter += 1
                    
                    # Convert to mono for analysis if needed
                    if channels > 1:
                        mono_chunk = np.mean(chunk, axis=1)
                    else:
                        mono_chunk = chunk.flatten()
                    
                    # First pass: quick energy check (avoid processing noise)
                    energy = np.sqrt(np.mean(mono_chunk ** 2))
                    
                    is_speech = False
                    
                    if energy < energy_threshold:
                        # Definitely too quiet to be speech
                        is_speech = False
                    elif use_whisper_vad and whisper_model:
                        # Energy detected, verify with Whisper VAD
                        try:
                            # Run Whisper with VAD filter
                            # If VAD detects speech, segments will be returned
                            segments, info = whisper_model.transcribe(
                                mono_chunk,
                                vad_filter=True,
                                vad_parameters=dict(
                                    min_silence_duration_ms=300,
                                    threshold=0.5
                                )
                            )
                            
                            # Check if any speech segments were detected
                            # We don't need the text, just whether speech was detected
                            segment_list = list(segments)
                            is_speech = len(segment_list) > 0
                            
                            if is_speech:
                                speech_detected = True
                                log.debug(f"Speech detected in chunk {chunk_counter}")
                            
                        except Exception as e:
                            log.warning(f"Whisper VAD error: {e}, using energy fallback")
                            # Fallback to energy-based if Whisper fails
                            is_speech = energy >= energy_threshold
                    else:
                        # Energy-based only
                        is_speech = energy >= energy_threshold
                    
                    # Update silence counter
                    if is_speech:
                        silence_counter = 0  # Reset on speech
                    else:
                        silence_counter += 1
                    
                    # Stop conditions
                    # Only stop if we've detected speech at least once
                    if chunk_counter >= min_chunks and speech_detected:
                        if silence_counter >= silence_chunks_needed:
                            log.debug(f"No speech for {silence_duration}s after {chunk_counter * chunk_duration:.1f}s")
                            break
                    
                    if chunk_counter >= max_chunks:
                        log.debug(f"Max duration {max_duration}s reached")
                        break
                        
                except queue.Empty:
                    log.warning("Audio queue timeout")
                    break
        
        if not chunks:
            log.warning("No audio recorded")
            return None
        
        # Concatenate all chunks
        recording = np.concatenate(chunks, axis=0)
        
        # Prepend pre-roll audio if available
        if preroll_audio is not None:
            log.debug(f"Prepending {len(preroll_audio)} samples of pre-roll audio")
            recording = np.concatenate([preroll_audio, recording], axis=0)
        
        # Convert to mono if stereo
        if channels > 1:
            recording = np.mean(recording, axis=1)
        
        duration = len(recording) / sample_rate
        log.debug(f"Recorded {duration:.1f}s of audio (speech_detected={speech_detected})")
        
        return recording.flatten()
        
    except Exception as e:
        log.error(f"Streaming recording error: {e}")
        return None
