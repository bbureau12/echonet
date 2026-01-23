from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="ECHONET_", env_file=".env", extra="ignore")

    host: str = "0.0.0.0"
    port: int = 8123

    api_key: str = "dev-change-me"
    # If set, /register requires X-Admin-Key to match
    admin_key: str | None = None

    session_timeout_s: int = 25

    cancel_phrases: str = "cancel,never mind,nevermind,stop listening"

    forward_strip_trigger: bool = True
    http_timeout_s: float = 3.0
    
    # Database path for target registry
    db_path: str = "echonet_registry.db"
    
    # Initial state on startup
    initial_listen_mode: str = "trigger"  # "inactive", "trigger", or "active"
    
    # ASR (Faster Whisper) settings
    whisper_model: str = "base"  # tiny, base, small, medium, large-v2, large-v3
    whisper_device: str = "cpu"  # cpu or cuda
    whisper_compute_type: str = "int8"  # int8 for CPU, float16 for GPU
    whisper_language: str = "en"  # Language code or "auto" for auto-detection
    
    # Audio device settings
    audio_device_index: int = 0  # Default audio input device index (0 = first device or system default)
    audio_sample_rate: int = 16000  # Sample rate in Hz (16kHz is good for speech recognition)
    audio_channels: int = 1  # Number of channels (1 = mono, 2 = stereo)
    
    # Voice Activity Detection (VAD) settings
    audio_silence_duration: float = 1.0  # Seconds of silence before stopping recording
    audio_min_duration: float = 0.5  # Minimum recording duration in seconds
    audio_max_duration: float = 30.0  # Maximum recording duration in seconds (safety timeout)
    audio_energy_threshold: float = 0.01  # Energy threshold for silence detection (0.0-1.0)
    audio_use_whisper_vad: bool = True  # Use Faster Whisper's VAD for speech detection (more accurate than energy-only)
    
    # Echonet event posting
    echonet_source_id: str = "microphone"
    echonet_room: str = "default"
    
    # Testing settings
    test_mode: bool = False  # Use pre-recorded audio files instead of microphone
    test_audio_dir: str = "test_audio"  # Directory containing test WAV files
    test_loop_delay: float = 2.0  # Seconds between processing test files
    
    # Discovery settings (mDNS)
    discovery_enabled: bool = True
    discovery_name: str = "Echonet"
    discovery_host: str = "echonet"
    discovery_zone: str = "home"
    discovery_subzone: str = "main-floor"
    
    # Security settings
    allowlist: str = "localhost,127.0.0.1"  # Comma-separated IPs and DNS names
    rate_limit_per_min: int = 60


settings = Settings()
