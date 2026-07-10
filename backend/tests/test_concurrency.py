"""
Unit tests for Whisper and Ollama concurrency semaphores.
Mocks only the time-consuming model execution to assert that requests
are serialized and run within the semaphore limits.
"""
from __future__ import annotations

import asyncio
import time
from unittest.mock import patch

import httpx
import pytest

from briefai.routers import transcription as api_transcription
from briefai.routers import summarization as api_summarization
from briefai.main import app
from briefai.schemas import TranscriptionResult

# ── Session state for tracking transcription intervals ───────────────────────
active_whisper = 0
max_whisper = 0
whisper_intervals = []

def mock_transcribe_file(audio_path, language=None, beam_size=5):
    """Mock Whisper transcription to simulate heavy blocking work."""
    global active_whisper, max_whisper
    active_whisper += 1
    max_whisper = max(max_whisper, active_whisper)
    
    start_time = time.perf_counter()
    time.sleep(0.15)  # Simulate CPU/GPU bound blocking work (runs in thread pool)
    end_time = time.perf_counter()
    
    active_whisper -= 1
    whisper_intervals.append((start_time, end_time))
    
    return TranscriptionResult(
        transcript="mocked meeting transcript.",
        segments=[],
        language="en",
        duration_seconds=1.5
    )


# ── Session state for tracking summarization intervals ───────────────────────
active_ollama = 0
max_ollama = 0
ollama_intervals = []

async def mock_generate(model, prompt, system_prompt=None, temperature=0.0, options=None):
    """Mock Ollama API call to simulate asynchronous generation delays."""
    from briefai.services.ollama_service import get_ollama_semaphore
    async with get_ollama_semaphore():
        global active_ollama, max_ollama
        active_ollama += 1
        max_ollama = max(max_ollama, active_ollama)
        
        start_time = time.perf_counter()
        await asyncio.sleep(0.15)  # Simulate network/inference async delay
        end_time = time.perf_counter()
        
        active_ollama -= 1
        ollama_intervals.append((start_time, end_time))
        
        return {
            "text": "mocked summary output.",
            "input_tokens": 15,
            "output_tokens": 20,
            "duration_ns": 1500000000
        }


# ── Concurrency Tests ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_whisper_concurrency_serialization():
    """Verify that multiple concurrent transcription uploads are serialized by the Whisper semaphore."""
    global active_whisper, max_whisper, whisper_intervals
    active_whisper = 0
    max_whisper = 0
    whisper_intervals.clear()
    
    # Configure the router semaphore to a limit of 1 for serialization testing
    api_transcription.transcription_semaphore = asyncio.Semaphore(1)
    
    from briefai.services.whisper_service import WhisperService
    
    with patch.object(WhisperService, 'transcribe_file', side_effect=mock_transcribe_file):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            # Prepare files payload
            files = {"file": ("test.wav", b"fake audio binary data", "audio/wav")}
            
            # Fire both requests concurrently
            task1 = client.post("/api/v1/transcription/upload", files=files)
            task2 = client.post("/api/v1/transcription/upload", files=files)
            
            responses = await asyncio.gather(task1, task2)
            
            for r in responses:
                assert r.status_code == 200
                assert r.json()["transcript"] == "mocked meeting transcript."
            
            # 1. Assert that the maximum concurrent transcription count never exceeded 1
            assert max_whisper == 1, f"Expected concurrency limit 1, got {max_whisper}"
            
            # 2. Assert both executions completed
            assert len(whisper_intervals) == 2
            
            # 3. Assert timing serialization: Task B start time must be >= Task A end time (with minor thread dispatch buffer)
            intervals = sorted(whisper_intervals, key=lambda x: x[0])
            first_end = intervals[0][1]
            second_start = intervals[1][0]
            
            assert second_start >= first_end - 0.05, (
                f"Tasks ran concurrently! First end: {first_end}, second start: {second_start}"
            )


@pytest.mark.asyncio
async def test_ollama_concurrency_serialization():
    """Verify that multiple concurrent summarization requests are serialized by the Ollama semaphore."""
    import asyncio
    global active_ollama, max_ollama, ollama_intervals
    active_ollama = 0
    max_ollama = 0
    ollama_intervals.clear()
    
    # Configure the router semaphore to a limit of 1 for serialization testing
    from briefai.services import ollama_service
    ollama_service._ollama_semaphore = asyncio.Semaphore(1)
    
    with patch.object(ollama_service.OllamaService, 'generate', side_effect=mock_generate):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            payload = {
                "transcript": "Test transcript. Welcome to the team meeting.",
                "task": "summarize",
                "model": "qwen3:1.7b",
                "stream": False
            }
            
            # Fire requests concurrently
            task1 = client.post("/api/v1/summarization/process", json=payload)
            task2 = client.post("/api/v1/summarization/process", json=payload)
            
            responses = await asyncio.gather(task1, task2)
            
            for r in responses:
                assert r.status_code == 200
                assert r.json()["result"] == "mocked summary output."
            
            # 1. Assert that the maximum concurrent Ollama call count never exceeded 1
            assert max_ollama == 1, f"Expected concurrency limit 1, got {max_ollama}"
            
            # 2. Assert both runs finished
            assert len(ollama_intervals) == 2
            
            # 3. Assert timing serialization: Task B start >= Task A end (with minor thread dispatch buffer)
            intervals = sorted(ollama_intervals, key=lambda x: x[0])
            first_end = intervals[0][1]
            second_start = intervals[1][0]
            
            assert second_start >= first_end - 0.05, (
                f"Tasks ran concurrently! First end: {first_end}, second start: {second_start}"
            )
