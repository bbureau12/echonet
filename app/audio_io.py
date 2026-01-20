# audio_io.py
"""Audio input/output handling with device management."""

import asyncio
import logging
from dataclasses import dataclass
from typing import Optional
import numpy as np
import sounddevice as sd

log = logging.getLogger("echonet.audio")


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
