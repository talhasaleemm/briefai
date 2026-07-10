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

import asyncio
import json
import logging
import tempfile
from datetime import datetime, timezone
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
from sqlalchemy.orm import Session

from briefai.config import settings
from briefai.internal.db import get_db, SessionLocal
from briefai.utils.deps import get_current_user
from briefai.utils.security import decode_token
from briefai.models import User, Transcript
from briefai.schemas import TranscriptionResult, TranscriptOut
from briefai.services.whisper_service import WhisperService, get_whisper_service
from briefai.services.diarization_service import DiarizationService, get_diarization_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/transcription", tags=["transcription"])

# Concurrency limiting semaphore
transcription_semaphore = asyncio.Semaphore(settings.WHISPER_CONCURRENCY_LIMIT)

# Diarization concurrency & task anchoring
diarization_semaphore = asyncio.Semaphore(settings.DIARIZATION_CONCURRENCY_LIMIT)
_background_diarization_tasks: set[asyncio.Task] = set()

def _launch_diarization_task(coro) -> asyncio.Task:
    task = asyncio.create_task(coro)
    _background_diarization_tasks.add(task)
    task.add_done_callback(_background_diarization_tasks.discard)
    return task

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
    diarization_svc: DiarizationService = Depends(get_diarization_service),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
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
        "Received upload: '%s' (%d bytes, language=%s) from user %s",
        original_name,
        len(audio_bytes),
        language or "auto",
        current_user.username,
    )

    # Write to a named temp file so faster-whisper can use its file-path path
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(audio_bytes)
        tmp_path = Path(tmp.name)

    try:
        async with transcription_semaphore:
            result = await asyncio.to_thread(svc.transcribe_file, tmp_path, language=language)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    finally:
        tmp_path.unlink(missing_ok=True)

    # Save to database
    db_transcript = Transcript(
        user_id=current_user.id,
        title=original_name,
        content=result.transcript,
        diarization_status="pending" if settings.DIARIZATION_ENABLED else "none"
    )
    db.add(db_transcript)
    db.commit()
    db.refresh(db_transcript)

    # Launch async chunking for RAG
    from briefai.retrieval.rag_service import launch_chunking_task
    launch_chunking_task(db_transcript.id, "transcript", current_user.id, result.transcript, db_transcript.id)

    segments_out = [
        {"start": seg.start, "end": seg.end, "text": seg.text, "confidence": seg.confidence}
        for seg in result.segments
    ]

    if settings.DIARIZATION_ENABLED and diarization_svc.is_loaded is not False: # handles NullDiarizationService
        # Save audio bytes to a new temp file for the background task
        # We don't reuse the whisper tmp_path since it gets unlinked in the finally block above.
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as bg_tmp:
            bg_tmp.write(audio_bytes)
            bg_tmp_path = Path(bg_tmp.name)
        
        _launch_diarization_task(_run_diarization(db_transcript.id, bg_tmp_path, segments_out, diarization_svc))

    # Return result populated with database ID
    return TranscriptionResult(
        id=db_transcript.id,
        transcript=result.transcript,
        segments=segments_out,
        language=result.language,
        duration_seconds=result.duration_seconds,
        diarization_status=db_transcript.diarization_status,
        diarized_segments=[]
    )


# ── WebSocket: Real-Time Streaming ────────────────────────────────────────────

@router.websocket("/stream")
async def stream_transcription(
    websocket: WebSocket,
    svc: WhisperService = Depends(get_whisper_service),
    db: Session = Depends(get_db),
) -> None:
    """
    WebSocket endpoint for real-time audio streaming and incremental transcription.
    Enforces authentication by expecting a {"action": "auth", "token": "..."} message first.
    """
    await websocket.accept()
    logger.info("WebSocket connected from %s", websocket.client)

    # Send connection greeting before expecting auth payload to prevent deadlock
    await websocket.send_text(json.dumps({
        "type": "info",
        "message": "BriefAI stream connected. Please authenticate.",
    }))

    # 1. Authenticate WebSocket on connection open
    user: User | None = None
    try:
        auth_msg = await websocket.receive_text()
        auth_data = json.loads(auth_msg)
        if auth_data.get("action") != "auth" or not auth_data.get("token"):
            logger.warning("WebSocket handshake failed: missing action=auth or token")
            await websocket.close(code=3000)
            return
        
        token = auth_data["token"]
        try:
            payload = decode_token(token)
            if payload.get("type") != "access":
                raise ValueError("Invalid token type")
            user_id = int(payload["sub"])
        except Exception as e:
            logger.warning("WebSocket token verification failed: %s", e)
            await websocket.close(code=3000)
            return

        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            logger.warning("WebSocket user no longer exists: %d", user_id)
            await websocket.close(code=3000)
            return

        # Handshake success info
        await websocket.send_text(json.dumps({
            "type": "info",
            "message": f"Welcome {user.username}! Send float32 PCM mono at 16 kHz. Send '{{\"action\": \"stop\"}}' to finalize.",
        }))

    except Exception as e:
        logger.error("WebSocket auth handshake crashed: %s", e)
        await websocket.close(code=3000)
        return

    # ── Session state ──────────────────────────────────────────────────────────
    buffer: list[np.ndarray] = []     # accumulates float32 chunks
    sample_rate: int = STREAM_SAMPLE_RATE
    language: Optional[str] = None
    absolute_time_offset: float = 0.0

    # Session accumulators for final report
    session_segments: list[dict] = []
    session_text_parts: list[str] = []

    # VAD chunking settings (dynamic based on sample_rate, read from settings config)
    min_chunk_len = int(settings.STREAM_VAD_MIN_CHUNK_S * sample_rate)
    max_chunk_len = int(settings.STREAM_VAD_MAX_CHUNK_S * sample_rate)
    silence_window = int(settings.STREAM_VAD_SILENCE_WINDOW_S * sample_rate)
    silence_threshold = settings.STREAM_VAD_SILENCE_THRESHOLD

    async def _transcribe_stream_audio(audio_chunk: np.ndarray, final: bool) -> None:
        """Transcribes a clean sliced audio chunk and emits adjusted timestamps."""
        nonlocal absolute_time_offset
        if len(audio_chunk) == 0:
            if final:
                final_text = " ".join(session_text_parts).strip()
                db_transcript = Transcript(
                    user_id=user.id,
                    title=f"Live Session - {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')}",
                    content=final_text,
                )
                db.add(db_transcript)
                db.commit()
                db.refresh(db_transcript)

                await websocket.send_text(json.dumps({
                    "type": "final",
                    "id": db_transcript.id,
                    "transcript": final_text,
                    "segments": session_segments,
                    "language": language or "unknown",
                    "duration_seconds": round(absolute_time_offset, 3),
                }))
            return

        try:
            async with transcription_semaphore:
                result = await asyncio.to_thread(
                    svc.transcribe_array, audio_chunk, sample_rate=sample_rate, language=language
                )
        except Exception as exc:
            logger.error("Transcription error in WebSocket: %s", exc)
            await websocket.send_text(json.dumps({
                "type": "error",
                "message": f"Transcription failed: {exc}",
            }))
            return

        # Adjust segment timestamps to align with absolute stream timeline
        adjusted_segments = []
        
        for seg in result.segments:
            adjusted = seg.model_copy(update={
                "start": round(seg.start + absolute_time_offset, 3),
                "end": round(seg.end + absolute_time_offset, 3),
            })
            adjusted_segments.append(adjusted)
            
            # Save to session accumulators
            session_segments.append(adjusted.model_dump())
            session_text_parts.append(seg.text)

        # Update absolute timeline tracking
        absolute_time_offset += (len(audio_chunk) / sample_rate)

        # Send outputs
        if final:
            final_text = " ".join(session_text_parts).strip()
            db_transcript = Transcript(
                user_id=user.id,
                title=f"Live Session - {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')}",
                content=final_text,
            )
            db.add(db_transcript)
            db.commit()
            db.refresh(db_transcript)
            logger.info("Saved transcript ID %s to database.", db_transcript.id)

            # Launch async chunking for RAG
            from briefai.retrieval.rag_service import launch_chunking_task
            launch_chunking_task(db_transcript.id, "transcript", user.id, final_text, db_transcript.id)

            await websocket.send_text(json.dumps({
                "type": "final",
                "id": db_transcript.id,
                "transcript": final_text,
                "segments": session_segments,
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

                # ── Audio quality debug logging ────────────────────────────
                rms_dbg = float(np.sqrt(np.mean(chunk**2)))
                peak_dbg = float(np.max(np.abs(chunk)))
                dur_dbg = n_samples / sample_rate
                logger.info(
                    "[AUDIO DEBUG] chunk: %d samples (%.2fs) | RMS=%.4f | Peak=%.4f | "
                    "non-zero=%d/%d",
                    n_samples, dur_dbg, rms_dbg, peak_dbg,
                    int(np.count_nonzero(np.abs(chunk) > 1e-5)), n_samples,
                )
                if rms_dbg < 0.001:
                    logger.warning(
                        "[AUDIO DEBUG] Very low RMS=%.6f — audio may be silence or near-zero. "
                        "Whisper will hallucinate on silent audio.", rms_dbg
                    )
                # ── End audio debug ────────────────────────────────────────

                buffer.append(chunk)

                total_samples = sum(len(c) for c in buffer)

                # Check if we can slice at a natural speech boundary (VAD)
                if total_samples >= min_chunk_len:
                    # Look back to find where energy drops below threshold (silence/pause)
                    full_chunk = np.concatenate(buffer, axis=0)
                    
                    split_idx = -1
                    # Search silence in the last window
                    search_start = len(full_chunk) - silence_window
                    if search_start > min_chunk_len:
                        for idx in range(search_start, len(full_chunk) - 1600, 1600):
                            window = full_chunk[idx : idx + 1600]
                            rms = np.sqrt(np.mean(window**2))
                            if rms < silence_threshold:
                                split_idx = idx + 800  # split middle of window
                                break

                    # Force split if max length is reached
                    if split_idx == -1 and total_samples >= max_chunk_len:
                        split_idx = max_chunk_len

                    if split_idx != -1:
                        to_process = full_chunk[:split_idx]
                        to_keep = full_chunk[split_idx:]
                        
                        buffer = [to_keep]
                        await _transcribe_stream_audio(to_process, final=False)

            # ── Text: control actions ─────────────────────────────────────────
            elif "text" in msg and msg["text"]:
                try:
                    ctrl = json.loads(msg["text"])
                except json.JSONDecodeError:
                    continue

                action = ctrl.get("action")
                
                if action == "config":
                    sample_rate = int(ctrl.get("sample_rate", STREAM_SAMPLE_RATE))
                    language = ctrl.get("language") or None
                    
                    # Recalculate VAD configurations dynamically based on new sample rate
                    min_chunk_len = int(settings.STREAM_VAD_MIN_CHUNK_S * sample_rate)
                    max_chunk_len = int(settings.STREAM_VAD_MAX_CHUNK_S * sample_rate)
                    silence_window = int(settings.STREAM_VAD_SILENCE_WINDOW_S * sample_rate)
                    
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


# ── REST: Transcript History & Management ──────────────────────────────────────

@router.get(
    "/",
    response_model=list[TranscriptOut],
    summary="List transcripts owned by the authenticated user",
)
async def list_transcripts(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[Transcript]:
    """Retrieve all saved transcripts for the current authenticated user, ordered by creation date."""
    return (
        db.query(Transcript)
        .filter(Transcript.user_id == current_user.id)
        .order_by(Transcript.created_at.desc())
        .all()
    )


@router.get(
    "/{transcript_id}",
    response_model=TranscriptOut,
    summary="Get a transcript by ID",
)
async def get_transcript(
    transcript_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Transcript:
    """
    Retrieve a specific transcript by ID.
    Enforces strict user isolation: if the transcript belongs to another user,
    returns a 404 Not Found to prevent ID scanning/enumeration.
    """
    transcript = (
        db.query(Transcript)
        .filter(Transcript.id == transcript_id, Transcript.user_id == current_user.id)
        .first()
    )
    if not transcript:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Transcript not found.",
        )
    return transcript


@router.delete(
    "/{transcript_id}",
    summary="Delete a transcript by ID",
)
async def delete_transcript(
    transcript_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, str]:
    """
    Delete a specific transcript by ID.
    Enforces strict user isolation: if the transcript belongs to another user,
    returns a 404 Not Found.
    """
    transcript = (
        db.query(Transcript)
        .filter(Transcript.id == transcript_id, Transcript.user_id == current_user.id)
        .first()
    )
    if not transcript:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Transcript not found.",
        )
    
    db.delete(transcript)
    db.commit()
    return {"detail": "Transcript successfully deleted."}


# ── REST: Diarization ────────────────────────────────────────────────────────

async def _run_diarization(transcript_id: int, audio_path: Path, whisper_segs: list[dict], diarization_svc: DiarizationService) -> None:
    """Background task to extract speaker embeddings and cluster them."""
    # Obtain a fresh database session since the request context is closed
    db_gen = get_db()
    db = next(db_gen)
    transcript = None
    try:
        transcript = db.query(Transcript).filter(Transcript.id == transcript_id).first()
        if not transcript:
            return

        async with diarization_semaphore:
            labeled = await asyncio.to_thread(
                diarization_svc.diarize_segments, audio_path, whisper_segs
            )
            
        transcript.diarized_segments = labeled
        transcript.diarization_status = "complete"
        db.commit()
    except Exception as exc:
        logger.error("Diarization failed for transcript %d: %s", transcript_id, exc, exc_info=True)
        if transcript:
            transcript.diarization_status = "failed"
            db.commit()
    finally:
        audio_path.unlink(missing_ok=True)
        db_gen.close()


@router.get(
    "/{transcript_id}/diarization",
    response_model=dict,
    summary="Get diarization status and segments for a transcript",
)
async def get_transcript_diarization(
    transcript_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """
    Retrieve diarization state. Returns 404 if the transcript belongs to another user.
    """
    transcript = (
        db.query(Transcript)
        .filter(Transcript.id == transcript_id, Transcript.user_id == current_user.id)
        .first()
    )
    if not transcript:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Transcript not found.",
        )
    return {
        "diarization_status": transcript.diarization_status,
        "diarized_segments": transcript.diarized_segments or []
    }

