"""
Application configuration — reads from .env file via pydantic-settings.
"""
from functools import lru_cache
from typing import List

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


from pathlib import Path

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(Path(__file__).parent.parent / ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # App
    APP_NAME: str = "BriefAI"
    APP_ENV: str = "development"
    DEBUG: bool = False  # Must be explicitly enabled via .env; defaults secure-off
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # CORS — accepts a comma-separated string from env, converts to list
    CORS_ORIGINS: List[str] = ["http://localhost:5173", "http://localhost:3000"]

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors_origins(cls, v):
        if isinstance(v, str):
            v = v.strip()
            if v.startswith("["):
                import json
                return json.loads(v)
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return v

    # Database
    DATABASE_URL: str = "sqlite:///./briefai.db"

    # Security
    # JWT_SECRET_KEY MUST be set in .env (no hardcoded default - app fails to start if missing)
    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7


    # Whisper
    WHISPER_MODEL_SIZE: str = "base"
    WHISPER_DEVICE: str = "cpu"
    WHISPER_COMPUTE_TYPE: str = "int8"
    WHISPER_LANGUAGE: str = ""
    WHISPER_CONCURRENCY_LIMIT: int = 2

    # Ollama
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_SUMMARIZER_MODEL: str = "qwen3:1.7b"
    OLLAMA_TRANSLATOR_MODEL: str = "llama3.2:1b"
    OLLAMA_TIMEOUT: int = 120
    OLLAMA_CONCURRENCY_LIMIT: int = 1

    # WebSocket Streaming VAD Chunker Settings
    STREAM_VAD_MIN_CHUNK_S: float = 3.0
    STREAM_VAD_MAX_CHUNK_S: float = 8.0
    STREAM_VAD_SILENCE_WINDOW_S: float = 0.5
    STREAM_VAD_SILENCE_THRESHOLD: float = 0.015

    # Diarization
    DIARIZATION_ENABLED: bool = True
    DIARIZATION_CONCURRENCY_LIMIT: int = 1
    DIARIZATION_MIN_SPEAKERS: int = 1
    DIARIZATION_MAX_SPEAKERS: int = 8
    DIARIZATION_COSINE_THRESHOLD: float = 0.5

    # Logging
    LOG_LEVEL: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    """Cached settings singleton — call this everywhere instead of instantiating directly."""
    return Settings()


# Module-level convenience alias
settings = get_settings()
