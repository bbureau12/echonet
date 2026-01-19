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
    initial_listen_mode: str = "trigger"  # "trigger" or "active"
    
    # ASR (Faster Whisper) settings
    whisper_model: str = "base"  # tiny, base, small, medium, large-v2, large-v3
    whisper_device: str = "cpu"  # cpu or cuda
    whisper_compute_type: str = "int8"  # int8 for CPU, float16 for GPU
    whisper_language: str = "en"  # Language code or "auto" for auto-detection
    
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
