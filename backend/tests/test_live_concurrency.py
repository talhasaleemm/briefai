"""
E2E Integration Concurrency Tests.
Tests the real running endpoints (no mocking) under concurrent request loads.
Ensures that requests serialize and resolve successfully without server crashes or timeouts.
"""
from __future__ import annotations

import asyncio
from pathlib import Path

import httpx
import pytest

from app.api import summarization as api_summarization
from app.api import transcription as api_transcription
from app.core.config import settings
from app.main import app


@pytest.fixture(scope="module")
def ollama_status() -> tuple[bool, list[str]]:
    """Fixture to verify if local Ollama is active and query installed models."""
    try:
        r = httpx.get(f"{settings.OLLAMA_BASE_URL}/api/tags", timeout=2.0)
        if r.status_code == 200:
            models = [m["name"] for m in r.json().get("models", [])]
            return True, models
    except Exception:
        pass
    return False, []


@pytest.mark.asyncio
async def test_live_ollama_concurrency(ollama_status):
    """Fire two real, concurrent requests to the Ollama summarization route."""
    import asyncio
    is_active, installed_models = ollama_status
    if not is_active:
        pytest.skip("Local Ollama service is not running. Skipped E2E live test.")
        
    target_model = settings.OLLAMA_SUMMARIZER_MODEL
    # Fallback to any model if configured one is not present
    if target_model not in installed_models and f"{target_model}:latest" not in installed_models:
        if installed_models:
            target_model = installed_models[0]
            print(f"[live test] Configured model not found. Using fallback model: {target_model}")
        else:
            pytest.skip("Ollama has no models installed. Skipping E2E live test.")

    # Configure the router semaphore to 1 to force queuing
    from app.services import ollama_service
    ollama_service._ollama_semaphore = asyncio.Semaphore(1)
    
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test", timeout=120.0) as client:
        payload = {
            "transcript": (
                "Meeting Notes. Topic: BriefAI platform enhancements. "
                "We need to optimize backend event loops and create beautiful visual components. "
                "Action item: implement thread offloading. Meeting adjourned."
            ),
            "task": "summarize",
            "model": target_model,
            "stream": False
        }
        
        # Fire two real concurrent requests
        task1 = client.post("/api/v1/summarization/process", json=payload)
        task2 = client.post("/api/v1/summarization/process", json=payload)
        
        responses = await asyncio.gather(task1, task2)
        
        for r in responses:
            assert r.status_code == 200
            data = r.json()
            assert "result" in data
            assert len(data["result"].strip()) > 0
            print(f"[live test] Request resolved successfully in {data['latency_ms']} ms")


@pytest.mark.asyncio
async def test_live_whisper_concurrency(sample_wav: Path):
    """Fire two real, concurrent requests to the Whisper transcription route using the generated WAV file."""
    assert sample_wav.exists()
    
    # Configure the router semaphore to 1 to force queuing
    api_transcription.transcription_semaphore = asyncio.Semaphore(1)
    
    # Read WAV bytes
    with open(sample_wav, "rb") as f:
        wav_bytes = f.read()

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test", timeout=90.0) as client:
        files1 = {"file": ("test1.wav", wav_bytes, "audio/wav")}
        files2 = {"file": ("test2.wav", wav_bytes, "audio/wav")}
        
        # Fire concurrent transcription requests
        task1 = client.post("/api/v1/transcription/upload", files=files1)
        task2 = client.post("/api/v1/transcription/upload", files=files2)
        
        responses = await asyncio.gather(task1, task2)
        
        for r in responses:
            assert r.status_code == 200
            data = r.json()
            assert "transcript" in data
            assert len(data["transcript"].strip()) > 0
            print(f"[live test] Transcription resolved successfully: {data['transcript'][:50]}...")
