"""
Application configuration — reads from .env file via pydantic-settings.
"""
from functools import lru_cache
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # App
    APP_NAME: str = "BriefAI"
    APP_ENV: str = "development"
    DEBUG: bool = True
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # CORS — accepts a comma-separated string from env, converts to list
    CORS_ORIGINS: List[str] = ["http://localhost:5173", "http://localhost:3000"]

    # Whisper
    WHISPER_MODEL_SIZE: str = "base"
    WHISPER_DEVICE: str = "cpu"
    WHISPER_COMPUTE_TYPE: str = "int8"
    WHISPER_LANGUAGE: str = ""

    # Ollama
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_SUMMARIZER_MODEL: str = "qwen3:1.7b"
    OLLAMA_TRANSLATOR_MODEL: str = "llama3.2:1b"
    OLLAMA_TIMEOUT: int = 120

    # WebSocket Streaming VAD Chunker Settings
    STREAM_VAD_MIN_CHUNK_S: float = 3.0
    STREAM_VAD_MAX_CHUNK_S: float = 8.0
    STREAM_VAD_SILENCE_WINDOW_S: float = 0.5
    STREAM_VAD_SILENCE_THRESHOLD: float = 0.015

    # Logging
    LOG_LEVEL: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    """Cached settings singleton — call this everywhere instead of instantiating directly."""
    return Settings()


# Module-level convenience alias
settings = get_settings()
