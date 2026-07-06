"""
Transcription API router.

Endpoints
---------
POST  /api/v1/transcription/upload   — upload an audio file, receive full transcript
WS    /api/v1/transcription/stream   — stream raw PCM float32 audio, receive incremental segments

WebSocket Protocol
------------------
Client → Server:
  Binary  : Raw float32 PCM audio chunks, mono, 16 kHz (default).
            Each chunk should be at least 0.5 s (≥ 8 000 samples).
  Text    : JSON control message, one of:
              {"action": "config", "sample_rate": 16000, "language": "en"}
              {"action": "stop"}   — flush buffer, return final result, close

Server → Client (all JSON text):
  {"type": "info",    "message": "..."}
  {"type": "segment", "text": "...", "start": 0.0, "end": 2.1, "confidence": -0.3}
  {"type": "final",   "transcript": "...", "segments": [...], "language": "en", "duration_seconds": 10.0}
  {"type": "error",   "message": "..."}
"""
from __future__ import annotations

import json
import logging
import tempfile
from pathlib import Path
from typing import Optional

import numpy as np
from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    Query,
    UploadFile,
    WebSocket,
    WebSocketDisconnect,
    status,
)

from app.models.schemas import TranscriptionResult
from app.services.whisper_service import WhisperService, get_whisper_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/transcription", tags=["transcription"])

# Formats that faster-whisper (via ffmpeg) can handle
SUPPORTED_FORMATS = frozenset({
    ".wav", ".mp3", ".flac", ".ogg", ".opus", ".m4a", ".webm", ".mp4", ".aac"
})

# Accumulate 5 s of audio before an incremental transcription tick
STREAM_CHUNK_SECONDS = 5
STREAM_SAMPLE_RATE = 16_000
STREAM_CHUNK_SAMPLES = STREAM_CHUNK_SECONDS * STREAM_SAMPLE_RATE


# ── REST: File Upload ──────────────────────────────────────────────────────────

@router.post(
    "/upload",
    response_model=TranscriptionResult,
    summary="Transcribe an uploaded audio file",
    response_description="Full transcription with per-segment timestamps",
)
async def upload_transcription(
    file: UploadFile = File(..., description="Audio file (WAV, MP3, FLAC, OGG, M4A, …)"),
    language: Optional[str] = Query(
        default=None,
        description="ISO 639-1 language code (e.g. 'en', 'fr', 'ar'). Auto-detected when omitted.",
        min_length=2,
        max_length=5,
    ),
    svc: WhisperService = Depends(get_whisper_service),
) -> TranscriptionResult:
    """
    Upload an audio file and receive a structured transcription.

    - **file** — WAV / MP3 / FLAC / OGG / M4A / WebM (max ~50 MB recommended for CPU)
    - **language** — optional; auto-detected from the first 30 s when not specified
    """
    original_name = file.filename or "audio.wav"
    suffix = Path(original_name).suffix.lower()

    if suffix not in SUPPORTED_FORMATS:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=(
                f"Format '{suffix}' is not supported. "
                f"Accepted: {sorted(SUPPORTED_FORMATS)}"
            ),
        )

    audio_bytes = await file.read()
    if not audio_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty.",
        )

    logger.info(
        "Received upload: '%s' (%d bytes, language=%s)",
        original_name,
        len(audio_bytes),
        language or "auto",
    )

    # Write to a named temp file so faster-whisper can use its file-path path
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(audio_bytes)
        tmp_path = Path(tmp.name)

    try:
        result = svc.transcribe_file(tmp_path, language=language)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    finally:
        tmp_path.unlink(missing_ok=True)

    return result


# ── WebSocket: Real-Time Streaming ────────────────────────────────────────────

@router.websocket("/stream")
async def stream_transcription(
    websocket: WebSocket,
    svc: WhisperService = Depends(get_whisper_service),
) -> None:
    """
    WebSocket endpoint for real-time audio streaming and incremental transcription.

    See module docstring for the full client ↔ server protocol.
    """
    await websocket.accept()
    logger.info("WebSocket connected from %s", websocket.client)

    await websocket.send_text(json.dumps({
        "type": "info",
        "message": (
            "BriefAI stream connected. "
            "Send float32 PCM mono at 16 kHz. "
            "Text '{\"action\": \"stop\"}' to finalise."
        ),
    }))

    # ── Session state ──────────────────────────────────────────────────────────
    buffer: list[np.ndarray] = []     # accumulates float32 chunks
    sample_rate: int = STREAM_SAMPLE_RATE
    language: Optional[str] = None
    absolute_time_offset: float = 0.0

    # VAD chunking settings (dynamic based on sample_rate)
    min_chunk_len = 3 * sample_rate
    max_chunk_len = 8 * sample_rate
    silence_window = int(0.5 * sample_rate)
    silence_threshold = 0.015

    async def _transcribe_stream_audio(audio_chunk: np.ndarray, final: bool) -> None:
        """Transcribes a clean sliced audio chunk and emits adjusted timestamps."""
        nonlocal absolute_time_offset
        if len(audio_chunk) == 0:
            if final:
                await websocket.send_text(json.dumps({
                    "type": "final",
                    "transcript": "",
                    "segments": [],
                    "language": "unknown",
                    "duration_seconds": round(absolute_time_offset, 3),
                }))
            return

        try:
            result = svc.transcribe_array(audio_chunk, sample_rate=sample_rate, language=language)
        except Exception as exc:
            logger.error("Transcription error in WebSocket: %s", exc)
            await websocket.send_text(json.dumps({
                "type": "error",
                "message": f"Transcription failed: {exc}",
            }))
            return

        # Adjust segment timestamps to align with absolute stream timeline
        adjusted_segments = []
        text_parts = []
        
        for seg in result.segments:
            adjusted = seg.model_copy(update={
                "start": round(seg.start + absolute_time_offset, 3),
                "end": round(seg.end + absolute_time_offset, 3),
            })
            adjusted_segments.append(adjusted)
            text_parts.append(seg.text)

        # Update absolute timeline tracking
        absolute_time_offset += (len(audio_chunk) / sample_rate)

        # Send outputs
        if final:
            await websocket.send_text(json.dumps({
                "type": "final",
                "transcript": " ".join(text_parts).strip(),
                "segments": [s.model_dump() for s in adjusted_segments],
                "language": result.language,
                "duration_seconds": round(absolute_time_offset, 3),
            }))
        else:
            for s in adjusted_segments:
                await websocket.send_text(json.dumps({
                    "type": "segment",
                    "text": s.text,
                    "start": s.start,
                    "end": s.end,
                    "confidence": s.confidence,
                }))

    # ── Message loop ───────────────────────────────────────────────────────────
    try:
        while True:
            msg = await websocket.receive()

            # ── Binary: audio chunk ───────────────────────────────────────────
            if "bytes" in msg and msg["bytes"]:
                raw: bytes = msg["bytes"]
                n_samples = len(raw) // 4  # float32 = 4 bytes
                if n_samples < 1:
                    continue

                chunk = np.frombuffer(raw, dtype=np.float32).copy()
                buffer.append(chunk)

                total_samples = sum(len(c) for c in buffer)

                # Check if we can slice at a natural speech boundary (VAD)
                if total_samples >= min_chunk_len:
                    combined = np.concatenate(buffer, axis=0)
                    
                    # Measure energy of the trailing 0.5s silence window
                    tail = combined[-silence_window:]
                    rms = np.sqrt(np.mean(tail**2)) if len(tail) > 0 else 0.0
                    
                    # Force process anyway if buffer grows too large to prevent latency bloat
                    force_slice = len(combined) >= max_chunk_len
                    
                    if rms < silence_threshold or force_slice:
                        buffer.clear()
                        await _transcribe_stream_audio(combined, final=False)

            # ── Text: control message ─────────────────────────────────────────
            elif "text" in msg and msg["text"]:
                try:
                    ctrl: dict = json.loads(msg["text"])
                except json.JSONDecodeError:
                    await websocket.send_text(json.dumps({
                        "type": "error",
                        "message": "Invalid JSON in control message.",
                    }))
                    continue

                action = ctrl.get("action", "")

                if action == "config":
                    sample_rate = int(ctrl.get("sample_rate", STREAM_SAMPLE_RATE))
                    language = ctrl.get("language") or None
                    
                    # Recalculate VAD configurations dynamically based on new sample rate
                    min_chunk_len = 3 * sample_rate
                    max_chunk_len = 8 * sample_rate
                    silence_window = int(0.5 * sample_rate)
                    
                    await websocket.send_text(json.dumps({
                        "type": "info",
                        "message": f"Session configured: sample_rate={sample_rate}, language={language or 'auto'}",
                    }))

                elif action == "stop":
                    if buffer:
                        remaining = np.concatenate(buffer, axis=0)
                    else:
                        remaining = np.array([], dtype=np.float32)
                    buffer.clear()
                    await _transcribe_stream_audio(remaining, final=True)
                    await websocket.close()
                    logger.info("WebSocket closed cleanly after stop signal.")
                    return

                else:
                    await websocket.send_text(json.dumps({
                        "type": "error",
                        "message": f"Unknown action '{action}'. Supported: 'config', 'stop'.",
                    }))

    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected.")
    except Exception as exc:
        logger.error("Unhandled WebSocket error: %s", exc, exc_info=True)
        try:
            await websocket.send_text(json.dumps({"type": "error", "message": str(exc)}))
        except Exception:
            pass
