"""
Integration tests for User Authentication, Data Isolation, and rate limiting.
Ensures per-user resource boundaries are strictly enforced and leakages are blocked.
"""
from __future__ import annotations

import json
import pytest
from fastapi import status
from fastapi.testclient import TestClient

from app.main import app
from app.models.database import User, Transcript, Summary
from app.core.security import create_access_token
from app.api.deps import get_current_user

# Test client
client = TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def clean_dependency_overrides():
    """Temporarily clears get_current_user auth override to test actual auth logic."""
    old_override = app.dependency_overrides.pop(get_current_user, None)
    yield
    if old_override is not None:
        app.dependency_overrides[get_current_user] = old_override


# ── Auth Endpoints Tests ──────────────────────────────────────────────────────

def test_user_registration_and_login(db, clean_dependency_overrides):
    """Test register and login workflow with password validation."""
    # 1. Register a user
    reg_payload = {
        "email": "alice@example.com",
        "username": "alice",
        "password": "supersecurepassword",
    }
    resp = client.post("/api/v1/auth/register", json=reg_payload)
    assert resp.status_code == status.HTTP_201_CREATED
    data = resp.json()
    assert data["username"] == "alice"
    assert data["email"] == "alice@example.com"
    assert "hashed_password" not in data

    # 2. Login
    login_payload = {
        "username_or_email": "alice",
        "password": "supersecurepassword",
    }
    resp = client.post("/api/v1/auth/login", json=login_payload)
    assert resp.status_code == status.HTTP_200_OK
    token_data = resp.json()
    assert "access_token" in token_data
    assert token_data["token_type"] == "bearer"
    # Verify HttpOnly refresh token cookie is set
    assert "refresh_token" in resp.cookies


def test_user_login_invalid_credentials(db, clean_dependency_overrides):
    """Verify unauthorized response on wrong username/email or password."""
    login_payload = {
        "username_or_email": "nonexistent",
        "password": "wrongpassword",
    }
    resp = client.post("/api/v1/auth/login", json=login_payload)
    assert resp.status_code == status.HTTP_401_UNAUTHORIZED
    assert resp.json()["detail"] == "Invalid username/email or password."


# ── Data Isolation & Ownership Boundary Tests ───────────────────────────────

def test_per_user_transcript_isolation(db):
    """
    Verify that GET, DELETE and summarization endpoints return 404 (Not Found)
    when accessing or referencing another user's transcript.
    """
    # 1. Create two users in test DB
    user_a = User(email="usera@test.com", username="usera", hashed_password="hashed")
    user_b = User(email="userb@test.com", username="userb", hashed_password="hashed")
    db.add_all([user_a, user_b])
    db.commit()

    # 2. Create a transcript owned by User B
    transcript_b = Transcript(
        user_id=user_b.id,
        title="Secret Meeting User B",
        content="This contains user b's private transcript contents.",
    )
    db.add(transcript_b)
    db.commit()

    # 3. Authenticate client as User A (override dependency)
    app.dependency_overrides[get_current_user] = lambda: user_a

    # ── Test 1: User A lists transcripts (should NOT see User B's transcript)
    resp = client.get("/api/v1/transcription/")
    assert resp.status_code == 200
    transcripts_list = resp.json()
    assert len(transcripts_list) == 0

    # ── Test 2: User A attempts GET user B's transcript_id (MUST return 404)
    resp = client.get(f"/api/v1/transcription/{transcript_b.id}")
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Transcript not found."

    # ── Test 3: User A attempts DELETE user B's transcript_id (MUST return 404)
    resp = client.delete(f"/api/v1/transcription/{transcript_b.id}")
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Transcript not found."

    # ── Test 4: User A attempts Summarize referencing user B's transcript_id (MUST return 404)
    # Mock Ollama Service inside this test
    from unittest.mock import AsyncMock, MagicMock
    from app.services.ollama_service import get_ollama_service, OllamaService
    mock_ollama = MagicMock(spec=OllamaService)
    app.dependency_overrides[get_ollama_service] = lambda: mock_ollama

    summarize_payload = {
        "transcript": "Let's summarize user b's secret transcript.",
        "transcript_id": transcript_b.id,
        "task": "summarize",
        "model": "qwen3:1.7b",
        "stream": False
    }
    resp = client.post("/api/v1/summarization/process", json=summarize_payload)
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Transcript not found."
    app.dependency_overrides.pop(get_ollama_service, None)


def test_per_user_summary_isolation(db):
    """Verify GET /summarization/history only returns the logged-in user's summaries."""
    user_a = User(email="usera@test.com", username="usera", hashed_password="hashed")
    user_b = User(email="userb@test.com", username="userb", hashed_password="hashed")
    db.add_all([user_a, user_b])
    db.commit()

    summary_b = Summary(
        user_id=user_b.id,
        transcript_id=None,
        task_type="summarize",
        model="qwen3:1.7b",
        result="Secret summary B",
    )
    db.add(summary_b)
    db.commit()

    # Authenticate as User A
    app.dependency_overrides[get_current_user] = lambda: user_a

    resp = client.get("/api/v1/summarization/history")
    assert resp.status_code == 200
    assert len(resp.json()) == 0


def test_login_rate_limiting(db, clean_dependency_overrides):
    """
    Verify rate limit fires at exactly attempt 6 (threshold = 5/5minutes).

    Expected sequence:
      Attempts 1-5  → 401 Unauthorized  (bad credentials; handler runs)
      Attempt  6+   → 429 Too Many Requests (slowapi blocks before handler)
    """
    # Register a real user so bcrypt verify_password runs normally
    reg_payload = {
        "email": "ratelimit@test.com",
        "username": "ratelimituser",
        "password": "correct_password",
    }
    reg_resp = client.post("/api/v1/auth/register", json=reg_payload)
    assert reg_resp.status_code == 201, f"Registration failed: {reg_resp.text}"

    # Fire 8 login attempts with the WRONG password
    login_payload = {
        "username_or_email": "ratelimituser",
        "password": "wrongpassword",
    }
    status_codes = []
    for i in range(1, 9):
        resp = client.post("/api/v1/auth/login", json=login_payload)
        status_codes.append(resp.status_code)
        print(f"  Attempt {i}: {resp.status_code}")

    print(f"  Full sequence: {status_codes}")

    # Attempts 1-5: bad credentials reach the handler → 401
    assert all(c == 401 for c in status_codes[:5]), (
        f"Expected 401 for attempts 1-5 (bad creds), got: {status_codes[:5]}"
    )
    # Attempt 6: rate limiter fires → 429
    assert status_codes[5] == 429, (
        f"Expected 429 at attempt 6 (threshold=5), got: {status_codes[5]}"
    )
    # Attempts 7-8: still rate-limited → 429
    assert all(c == 429 for c in status_codes[6:]), (
        f"Expected 429 for attempts 7+, got: {status_codes[6:]}"
    )



def test_true_e2e_jwt_isolation(db, clean_dependency_overrides):
    """
    E2E boundary check: registers A and B, obtains real JWTs,
    and asserts that User B cannot read or modify User A's data.
    """
    # 1. Register User A
    resp = client.post("/api/v1/auth/register", json={
        "email": "usera@realjwt.com",
        "username": "usera_jwt",
        "password": "usera_password"
    })
    assert resp.status_code == 201

    # 2. Register User B
    resp = client.post("/api/v1/auth/register", json={
        "email": "userb@realjwt.com",
        "username": "userb_jwt",
        "password": "userb_password"
    })
    assert resp.status_code == 201

    # 3. Login User A to get real A-JWT
    resp = client.post("/api/v1/auth/login", json={
        "username_or_email": "usera_jwt",
        "password": "usera_password"
    })
    assert resp.status_code == 200
    token_a = resp.json()["access_token"]

    # 4. Login User B to get real B-JWT
    resp = client.post("/api/v1/auth/login", json={
        "username_or_email": "userb_jwt",
        "password": "userb_password"
    })
    assert resp.status_code == 200
    token_b = resp.json()["access_token"]

    # 5. User A uploads a transcript (using real A-JWT)
    import io
    dummy_wav = io.BytesIO()
    # Simple valid 16-bit PCM header
    dummy_wav.write(b"RIFF\x24\x00\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00\x80\x3e\x00\x00\x00\x7d\x00\x00\x02\x00\x10\x00data\x00\x00\x00\x00")
    dummy_wav.seek(0)

    # Mock WhisperService for upload endpoint to return dummy transcript
    from unittest.mock import MagicMock
    from app.api.transcription import get_whisper_service, WhisperService
    mock_whisper = MagicMock(spec=WhisperService)
    mock_result = MagicMock()
    mock_result.transcript = "Hello world from User A"
    mock_result.segments = []
    mock_result.duration_seconds = 1.0
    mock_result.language = "en"
    mock_whisper.transcribe_file.return_value = mock_result
    app.dependency_overrides[get_whisper_service] = lambda: mock_whisper

    resp = client.post(
        "/api/v1/transcription/upload",
        files={"file": ("meeting.wav", dummy_wav, "audio/wav")},
        headers={"Authorization": f"Bearer {token_a}"}
    )
    assert resp.status_code == 200
    transcript_a_id = resp.json()["id"]
    app.dependency_overrides.pop(get_whisper_service, None)

    # 6. User B attempts to GET User A's transcript using User B's real JWT (MUST return 404)
    resp = client.get(
        f"/api/v1/transcription/{transcript_a_id}",
        headers={"Authorization": f"Bearer {token_b}"}
    )
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Transcript not found."

    # 7. User B attempts to DELETE User A's transcript using User B's real JWT (MUST return 404)
    resp = client.delete(
        f"/api/v1/transcription/{transcript_a_id}",
        headers={"Authorization": f"Bearer {token_b}"}
    )
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Transcript not found."

