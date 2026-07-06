"""
BriefAI Backend — FastAPI Application Entry Point
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings

app = FastAPI(
    title=settings.APP_NAME,
    description="Real-Time Meeting Transcription & Multilingual Summarization Platform",
    version="0.1.0",
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
    return {"status": "ok", "app": settings.APP_NAME, "version": "0.1.0"}


# ── Routers (wired in future stages) ─────────────────────────────────────────
# from app.api import transcription, summarization
# app.include_router(transcription.router, prefix="/api/v1", tags=["transcription"])
# app.include_router(summarization.router, prefix="/api/v1", tags=["summarization"])
