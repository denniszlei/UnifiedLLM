"""Application configuration."""

from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Database
    database_url: str = "sqlite:///./data/llm_manager.db"

    # Encryption (validated at startup by EncryptionService)
    encryption_key: Optional[str] = None

    # GPT-Load
    gptload_url: str = "http://localhost:3001"
    gptload_auth_key: Optional[str] = None

    # Application
    app_host: str = "0.0.0.0"
    app_port: int = 8000


settings = Settings()
