"""
BriefAI Backend — FastAPI Application Entry Point
"""
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings

logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)

app = FastAPI(
    title=settings.APP_NAME,
    description=(
        "Real-Time Meeting Transcription & Multilingual Summarization Platform. "
        "Upload audio or stream live microphone input; receive structured summaries, "
        "translations, and action items powered by faster-whisper and Ollama LLMs."
    ),
    version="0.2.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# ── CORS ─────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Health check ─────────────────────────────────────────────────────────────
@app.get("/health", tags=["system"])
async def health_check() -> dict:
    """Liveness probe — returns OK if the server is running."""
    return {"status": "ok", "app": settings.APP_NAME, "version": "0.2.0"}


# ── Routers ───────────────────────────────────────────────────────────────────
from app.api import transcription  # noqa: E402  (import after app init to avoid circular)
from app.api import summarization  # noqa: E402

app.include_router(transcription.router, prefix="/api/v1")
app.include_router(summarization.router, prefix="/api/v1")
