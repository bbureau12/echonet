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


settings = Settings()
