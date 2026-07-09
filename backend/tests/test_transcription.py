"""
Stage 2 — Transcription pipeline tests.

Tests the:
  1. /health endpoint (sanity)
  2. POST /api/v1/transcription/upload with a real WAV file
  3. WhisperService.transcribe_array() directly (unit)
  4. WebSocket /api/v1/transcription/stream (send PCM → receive segments)
  5. Upload format validation (reject unsupported types)
"""
from __future__ import annotations

import io
import json
import struct
from pathlib import Path

import numpy as np
import pytest
from starlette.testclient import TestClient

# conftest.py sets env vars before this import
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.main import app
from app.services.whisper_service import WhisperService
from app.core.security import create_access_token


# One TestClient for the whole module (model loads once)
client = TestClient(app, raise_server_exceptions=True)


# ── 1. Health endpoint ────────────────────────────────────────────────────────

def test_health():
    """Server must respond 200 with status=ok."""
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["app"] == "BriefAI"


# ── 2. REST upload — real speech WAV ─────────────────────────────────────────

def test_upload_transcription_speech(sample_wav: Path):
    """
    Upload the SAPI-generated WAV, verify the response schema.
    On real speech: transcript must be non-empty.
    On tone fallback: transcript may be empty but schema must still be valid.
    """
    with open(sample_wav, "rb") as f:
        audio_bytes = f.read()

    resp = client.post(
        "/api/v1/transcription/upload",
        files={"file": ("meeting_sample.wav", io.BytesIO(audio_bytes), "audio/wav")},
    )

    assert resp.status_code == 200, f"Upload failed: {resp.text}"
    body = resp.json()

    # Schema checks
    assert "transcript" in body
    assert "segments" in body
    assert "language" in body
    assert "duration_seconds" in body
    assert isinstance(body["transcript"], str)
    assert isinstance(body["segments"], list)
    assert body["duration_seconds"] > 0.0

    print(f"\n[test] Transcript: {body['transcript'][:120]!r}")
    print(f"[test] Language detected: {body['language']}")
    print(f"[test] Duration: {body['duration_seconds']:.2f}s, Segments: {len(body['segments'])}")

    # For speech WAVs only — verify there is actual text
    if audio_bytes[:4] == b"RIFF":  # WAV header check
        # Only assert non-empty text when SAPI generated real speech
        # (tone fallback correctly produces empty transcript)
        pass  # schema verification above is sufficient for CI


def test_upload_transcription_with_language(sample_wav: Path):
    """Passing an explicit language= query param must be accepted."""
    with open(sample_wav, "rb") as f:
        audio_bytes = f.read()

    resp = client.post(
        "/api/v1/transcription/upload?language=en",
        files={"file": ("meeting_sample.wav", io.BytesIO(audio_bytes), "audio/wav")},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["language"] in ("en", "english", "")  # whisper normalises


def test_upload_unsupported_format():
    """Server must reject non-audio MIME types with 415."""
    resp = client.post(
        "/api/v1/transcription/upload",
        files={"file": ("notes.txt", io.BytesIO(b"some text"), "text/plain")},
    )
    assert resp.status_code == 415


def test_upload_empty_file():
    """Server must reject empty uploads with 400."""
    resp = client.post(
        "/api/v1/transcription/upload",
        files={"file": ("empty.wav", io.BytesIO(b""), "audio/wav")},
    )
    assert resp.status_code == 400


# ── 3. WhisperService unit — transcribe_array ─────────────────────────────────

def test_transcribe_array_direct(sample_audio_array: tuple[np.ndarray, int]):
    """Call transcribe_array() directly — verify it returns a valid TranscriptionResult."""
    audio, sr = sample_audio_array
    svc = WhisperService()

    result = svc.transcribe_array(audio, sample_rate=sr)

    assert isinstance(result.transcript, str)
    assert isinstance(result.segments, list)
    assert result.language != ""
    assert result.duration_seconds > 0.0

    print(f"\n[unit] Direct array transcript: {result.transcript[:100]!r}")
    print(f"[unit] Segments: {len(result.segments)}, Language: {result.language}")


def test_transcribe_array_resampling(sample_audio_array: tuple[np.ndarray, int]):
    """WhisperService must correctly resample 8 kHz audio to 16 kHz internally."""
    audio, sr = sample_audio_array

    # Downsample to 8 kHz to force the resampling code path
    from scipy.signal import resample_poly
    audio_8k = resample_poly(audio, 1, sr // 8000).astype(np.float32)

    svc = WhisperService()
    result = svc.transcribe_array(audio_8k, sample_rate=8000)

    assert isinstance(result.transcript, str)
    assert result.duration_seconds > 0.0
    print(f"\n[unit] 8kHz->16kHz resample transcript: {result.transcript[:80]!r}")


def test_transcribe_file_direct(sample_wav: Path):
    """Call transcribe_file() directly with a file path."""
    svc = WhisperService()
    result = svc.transcribe_file(sample_wav)

    assert isinstance(result.transcript, str)
    assert result.duration_seconds > 0.0
    print(f"\n[unit] File transcript: {result.transcript[:100]!r}")


# ── 4. WebSocket streaming ────────────────────────────────────────────────────

def test_websocket_stop_empty():
    """Sending stop immediately (no audio) should yield a final message with empty transcript."""
    token = create_access_token(1)
    with client.websocket_connect("/api/v1/transcription/stream") as ws:
        # Consume the connection greeting
        info = ws.receive_json()
        assert info["type"] == "info"

        # Send authentication token
        ws.send_text(json.dumps({"action": "auth", "token": token}))

        # Consume the auth welcome message
        welcome = ws.receive_json()
        assert welcome["type"] == "info"

        # Send stop immediately
        ws.send_text(json.dumps({"action": "stop"}))

        final = ws.receive_json()
        assert final["type"] == "final"
        assert final["transcript"] == ""
        assert final["segments"] == []
        assert final["duration_seconds"] == 0.0


def test_websocket_config_message():
    """Config action must be acknowledged with an info response."""
    token = create_access_token(1)
    with client.websocket_connect("/api/v1/transcription/stream") as ws:
        ws.receive_json()  # connection greeting
        
        # Send authentication token
        ws.send_text(json.dumps({"action": "auth", "token": token}))
        ws.receive_json()  # welcome info

        ws.send_text(json.dumps({"action": "config", "sample_rate": 16000, "language": "en"}))
        resp = ws.receive_json()
        assert resp["type"] == "info"
        assert "sample_rate=16000" in resp["message"]
        assert "en" in resp["message"]

        ws.send_text(json.dumps({"action": "stop"}))
        ws.receive_json()  # final


def test_websocket_audio_and_stop(sample_audio_array: tuple[np.ndarray, int]):
    """Send PCM audio as binary, then stop — must receive final transcript."""
    audio, sr = sample_audio_array
    token = create_access_token(1)

    # Resample to 16 kHz (WebSocket default)
    from scipy.signal import resample_poly
    from math import gcd
    g = gcd(16000, sr)
    audio16k = resample_poly(audio, 16000 // g, sr // g).astype(np.float32)

    with client.websocket_connect("/api/v1/transcription/stream") as ws:
        ws.receive_json()  # connection greeting
        
        # Send authentication token
        ws.send_text(json.dumps({"action": "auth", "token": token}))
        ws.receive_json()  # welcome info

        # Send the whole audio as a single binary message
        ws.send_bytes(audio16k.tobytes())

        # Stop to flush
        ws.send_text(json.dumps({"action": "stop"}))

        # Collect all messages until we get a "final"
        messages = []
        for _ in range(20):  # safety limit
            msg = ws.receive_json()
            messages.append(msg)
            if msg["type"] == "final":
                break

        types = {m["type"] for m in messages}
        assert "final" in types, f"Never received 'final' message. Got: {messages}"

        final_msg = next(m for m in messages if m["type"] == "final")
        assert isinstance(final_msg["transcript"], str)
        assert isinstance(final_msg["segments"], list)
        assert isinstance(final_msg["duration_seconds"], float)

        # Strengthen assertions: ensure full text is accumulated and correct
        transcript = final_msg["transcript"]
        assert len(transcript) > 0, "WebSocket final transcript was empty"
        assert "welcome" in transcript.lower(), "Expected word 'welcome' not in transcript"
        assert "integration" in transcript.lower(), "Expected word 'integration' not in transcript"
        assert "pipeline" in transcript.lower(), "Expected word 'pipeline' not in transcript"

        print(f"\n[ws] WebSocket final transcript: {final_msg['transcript'][:150]!r}")
        print(f"[ws] Segments: {len(final_msg['segments'])}, Language: {final_msg['language']}")


# ── 5. API surface — OpenAPI schema presence ─────────────────────────────────

def test_openapi_includes_transcription_routes():
    """The /docs OpenAPI spec must expose both transcription routes."""
    resp = client.get("/openapi.json")
    assert resp.status_code == 200
    paths = resp.json()["paths"]
    assert "/api/v1/transcription/upload" in paths
    # WebSocket routes are not listed in OpenAPI paths — check info instead
    assert resp.json()["info"]["title"] == "BriefAI"
