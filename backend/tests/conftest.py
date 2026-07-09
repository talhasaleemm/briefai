"""
pytest conftest.py — shared fixtures and environment setup for all BriefAI tests.

Sets Whisper to 'tiny' model on CPU before any module imports occur,
so tests run fast without GPU and don't download large model checkpoints.
"""
from __future__ import annotations

import os
import struct
import subprocess
import wave
from pathlib import Path

import numpy as np
import pytest

# ── Force tiny model + CPU for all test sessions ─────────────────────────────
# These must be set BEFORE app.core.config is imported anywhere.
os.environ.setdefault("WHISPER_MODEL_SIZE", "tiny")
os.environ.setdefault("WHISPER_DEVICE", "cpu")
os.environ.setdefault("WHISPER_COMPUTE_TYPE", "int8")
os.environ.setdefault("OLLAMA_BASE_URL", "http://localhost:11434")


# ── WAV generation helpers ────────────────────────────────────────────────────

def _generate_speech_wav_windows(out_path: Path, text: str) -> bool:
    """
    Generate a WAV file from text using Windows SAPI (System.Speech).
    Returns True on success, False if SAPI is unavailable.
    """
    ps_script = f"""
Add-Type -AssemblyName System.Speech
$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer
$synth.SetOutputToWaveFile('{str(out_path).replace(chr(92), '/')}')
$synth.Rate = -1
$synth.Volume = 100
$synth.Speak("{text}")
$synth.Dispose()
Write-Host "SAPI_OK"
"""
    result = subprocess.run(
        ["powershell", "-NoProfile", "-Command", ps_script],
        capture_output=True,
        text=True,
        timeout=30,
    )
    return result.returncode == 0 and out_path.exists() and out_path.stat().st_size > 1000


def _generate_tone_wav(out_path: Path, duration_s: float = 3.0, sample_rate: int = 16000) -> Path:
    """
    Fallback: generate a 440 Hz sine-wave WAV (no real speech, but valid audio format).
    Used when Windows SAPI is unavailable (e.g., CI on Linux).
    """
    n = int(sample_rate * duration_s)
    t = np.linspace(0, duration_s, n, endpoint=False)
    samples = (np.sin(2 * np.pi * 440 * t) * 32767).astype(np.int16)
    with wave.open(str(out_path), "w") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(samples.tobytes())
    return out_path


# ── Session-scoped fixtures ───────────────────────────────────────────────────

@pytest.fixture(scope="session")
def sample_wav(tmp_path_factory) -> Path:
    """
    Real-speech WAV file, generated once per test session.

    On Windows: uses Windows SAPI (System.Speech) to synthesise a short meeting
    excerpt.  On other platforms (or if SAPI fails): falls back to a 440 Hz tone
    WAV so the test still exercises the full upload pipeline.
    """
    out = tmp_path_factory.mktemp("audio") / "meeting_sample.wav"

    meeting_text = (
        "Welcome to the BriefAI integration test. "
        "Today we will review the transcription pipeline "
        "and verify that faster-whisper returns accurate results. "
        "Action item one: confirm the API is working. "
        "Action item two: proceed to the next stage."
    )

    speech_ok = _generate_speech_wav_windows(out, meeting_text)
    if speech_ok:
        print(f"\n[fixture] Speech WAV generated via SAPI: {out} ({out.stat().st_size} bytes)")
    else:
        _generate_tone_wav(out)
        print(f"\n[fixture] Tone WAV generated (SAPI fallback): {out}")

    assert out.exists() and out.stat().st_size > 0, "WAV fixture generation failed completely"
    return out


@pytest.fixture(scope="session")
def sample_audio_array(sample_wav) -> tuple[np.ndarray, int]:
    """
    Read the sample WAV into a float32 NumPy array.
    Returns (audio_array, sample_rate).
    """
    import wave as wv

    with wv.open(str(sample_wav), "rb") as wf:
        n_frames = wf.getnframes()
        sampwidth = wf.getsampwidth()
        sample_rate = wf.getframerate()
        raw = wf.readframes(n_frames)

    if sampwidth == 2:
        samples = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
    elif sampwidth == 4:
        samples = np.frombuffer(raw, dtype=np.int32).astype(np.float32) / 2147483648.0
    else:
        samples = np.frombuffer(raw, dtype=np.uint8).astype(np.float32) / 128.0 - 1.0

    return samples, sample_rate


# ── Database & Authentication Test Overrides ─────────────────────────────────

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.core.database import Base, get_db
from app.api.deps import get_current_user
from app.models.database import User, Transcript, Summary

# File-based SQLite engine for robust test execution across threads and connection scopes
test_engine = create_engine(
    "sqlite:///./test_briefai.db",
    connect_args={"check_same_thread": False}
)
TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


@pytest.fixture(name="db", scope="function")
def db_fixture():
    """Create a clean, isolated database for a single test."""
    import os
    if os.path.exists("./test_briefai.db"):
        try:
            os.remove("./test_briefai.db")
        except Exception:
            pass
            
    Base.metadata.create_all(bind=test_engine)
    session = TestSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=test_engine)
        if os.path.exists("./test_briefai.db"):
            try:
                os.remove("./test_briefai.db")
            except Exception:
                pass


@pytest.fixture(autouse=True)
def reset_rate_limiter():
    """Reset slowapi rate limits before and after every test to keep test environment isolated."""
    from app.core.limiter import limiter
    limiter.reset()
    yield
    limiter.reset()


@pytest.fixture(autouse=True)
def override_db_dependency(db):
    """Automatically redirect all database sessions to the in-memory test DB."""
    from app.main import app
    def get_db_override():
        try:
            yield db
        finally:
            pass
    
    app.dependency_overrides[get_db] = get_db_override
    yield
    app.dependency_overrides.pop(get_db, None)


@pytest.fixture(autouse=True)
def default_auth_override(db):
    """Automatically mock user authentication to keep existing tests functioning."""
    from app.main import app
    
    # Insert default mock user into the fresh database
    default_user = User(
        email="default@test.com",
        username="defaulttestuser",
        hashed_password="mockhashedpassword"
    )
    db.add(default_user)
    db.commit()
    db.refresh(default_user)

    app.dependency_overrides[get_current_user] = lambda: default_user
    yield default_user
    app.dependency_overrides.pop(get_current_user, None)

