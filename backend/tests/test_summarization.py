"""
Integration and unit test suite for Stage 3 Ollama integration.
Uses FastAPI dependency overrides to mock local Ollama REST API responses,
ensuring tests run offline, reliably, and fast.
"""
from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import status
from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app
from app.models.schemas import ModelName, TaskType
from app.services.ollama_service import OllamaService, get_ollama_service

client = TestClient(app)


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def mock_ollama_service() -> MagicMock:
    """Fixture to mock OllamaService methods."""
    mock_svc = MagicMock(spec=OllamaService)
    # AsyncMock for non-streaming generate
    mock_svc.generate = AsyncMock()
    # Mock for streaming generate_stream
    mock_svc.generate_stream = MagicMock()
    return mock_svc


@pytest.fixture(autouse=True)
def setup_dependency_override(mock_ollama_service):
    """Override the get_ollama_service dependency automatically for all API tests."""
    app.dependency_overrides[get_ollama_service] = lambda: mock_ollama_service
    yield
    # Clean up overrides after each test
    app.dependency_overrides.clear()


# ── Summarization Route Tests ──────────────────────────────────────────────────

def test_process_summarize_success(mock_ollama_service):
    """Test successful non-streaming summarization request using Qwen3."""
    mock_ollama_service.generate.return_value = {
        "text": "This is a summary of the meeting about the AI integration.",
        "input_tokens": 12,
        "output_tokens": 10,
        "duration_ns": 1500000000,
    }

    req_body = {
        "transcript": "Welcome to the meeting. Today we discuss the integration of Whisper and Ollama.",
        "task": "summarize",
        "model": "qwen3:1.7b",
        "stream": False,
    }

    resp = client.post("/api/v1/summarization/process", json=req_body)
    assert resp.status_code == status.HTTP_200_OK
    
    body = resp.json()
    assert body["task"] == "summarize"
    assert body["model"] == "qwen3:1.7b"
    assert "AI integration" in body["result"]
    assert body["input_tokens"] == 12
    assert body["output_tokens"] == 10
    assert body["latency_ms"] > 0.0

    # Verify service was invoked with correct arguments
    mock_ollama_service.generate.assert_called_once()
    args, kwargs = mock_ollama_service.generate.call_args
    assert kwargs["model"] == "qwen3:1.7b"
    assert "concise summary" in kwargs["prompt"]


def test_process_translate_success(mock_ollama_service):
    """Test successful translation request to French using Llama 3.2."""
    mock_ollama_service.generate.return_value = {
        "text": "Bienvenue à la réunion.",
        "input_tokens": 10,
        "output_tokens": 8,
        "duration_ns": 900000000,
    }

    req_body = {
        "transcript": "Welcome to the meeting.",
        "task": "translate",
        "model": "llama3.2:1b",
        "target_language": "French",
        "stream": False,
    }

    resp = client.post("/api/v1/summarization/process", json=req_body)
    assert resp.status_code == status.HTTP_200_OK
    
    body = resp.json()
    assert body["task"] == "translate"
    assert body["model"] == "llama3.2:1b"
    assert "Bienvenue" in body["result"]

    # Verify service was invoked with correct arguments
    mock_ollama_service.generate.assert_called_once()
    args, kwargs = mock_ollama_service.generate.call_args
    assert kwargs["model"] == "llama3.2:1b"
    assert "translate the following meeting transcript to French" in kwargs["prompt"]


def test_process_streaming_success(mock_ollama_service):
    """Test streaming summarization request yielding token fragments."""
    # Mock the async generator for stream output
    async def mock_stream_generator(*args, **kwargs):
        chunks = [
            {"text": "Here ", "done": False},
            {"text": "is ", "done": False},
            {"text": "the summary.", "done": True},
        ]
        for chunk in chunks:
            yield chunk

    mock_ollama_service.generate_stream.side_effect = mock_stream_generator

    req_body = {
        "transcript": "Meeting discussion notes here.",
        "task": "summarize",
        "model": "qwen3:1.7b",
        "stream": True,
    }

    resp = client.post("/api/v1/summarization/process", json=req_body)
    assert resp.status_code == status.HTTP_200_OK
    assert resp.headers["content-type"].startswith("text/plain")
    
    # Read streamed text content
    text_output = resp.text
    assert text_output == "Here is the summary."
    mock_ollama_service.generate_stream.assert_called_once()


# ── OllamaService Integration Unit Tests ────────────────────────────────────────

@pytest.mark.asyncio
async def test_ollama_service_generate_payload():
    """Verify OllamaService formats API requests correctly and calls HTTP client."""
    svc = OllamaService(base_url="http://mock-ollama:11434")
    
    # Mock httpx AsyncClient post request
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.raise_for_status = MagicMock()
    mock_response.json = MagicMock(return_value={
        "response": "Hello World",
        "prompt_eval_count": 5,
        "eval_count": 4,
        "total_duration": 120000000,
    })

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_response
        
        res = await svc.generate(
            model="qwen3:1.7b",
            prompt="Write hello world",
            system_prompt="Be coding assistant",
            temperature=0.7
        )

        # Assert correct parsed output dict
        assert res["text"] == "Hello World"
        assert res["input_tokens"] == 5
        assert res["output_tokens"] == 4

        # Assert HTTP request format
        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        assert args[0] == "http://mock-ollama:11434/api/generate"
        
        json_payload = kwargs["json"]
        assert json_payload["model"] == "qwen3:1.7b"
        assert json_payload["prompt"] == "Write hello world"
        assert json_payload["system"] == "Be coding assistant"
        assert json_payload["options"]["temperature"] == 0.7
        assert json_payload["stream"] is False


# ── Live Integration Tests (executed when Ollama is running locally) ───────────

def is_ollama_running() -> bool:
    """Helper to detect if a local Ollama instance is active."""
    import socket
    try:
        with socket.create_connection(("127.0.0.1", 11434), timeout=0.5):
            return True
    except OSError:
        return False


@pytest.mark.skipif(not is_ollama_running(), reason="Ollama server is not active on localhost:11434")
def test_process_summarize_live():
    """Test live summarization endpoint against a running Ollama instance (Qwen3)."""
    # Clear any dependency overrides to hit the real Ollama service
    app.dependency_overrides.clear()

    req_body = {
        "transcript": (
            "Welcome to the Brief AI Integration Test. "
            "Today we will review the transcription pipeline "
            "and verify that faster-whisper returns accurate results. "
            "Action item one: confirm the API is working. "
            "Action item two: proceed to the next stage."
        ),
        "task": "summarize",
        "model": "qwen3:1.7b",
        "stream": False,
    }

    resp = client.post("/api/v1/summarization/process", json=req_body)
    assert resp.status_code == status.HTTP_200_OK
    
    body = resp.json()
    assert body["task"] == "summarize"
    assert body["model"] == "qwen3:1.7b"
    
    result = body["result"]
    assert len(result) > 20, f"Expected substantial summary, got: {result!r}"
    
    # Loose content-relevance check: must contain key words/concepts from input transcript
    result_lower = result.lower()
    relevance_keywords = ["brief", "pipeline", "transcription", "whisper", "test", "action", "api", "meeting"]
    matched = [w for w in relevance_keywords if w in result_lower]
    assert len(matched) >= 2, f"Summary relevance check failed. Matched keywords: {matched} in result: {result!r}"
    
    # Assert token stats and latency are present
    assert isinstance(body["input_tokens"], int)
    assert body["input_tokens"] > 0
    assert isinstance(body["output_tokens"], int)
    assert body["output_tokens"] > 0
    assert isinstance(body["latency_ms"], float)
    assert body["latency_ms"] > 0.0

    print(f"\n[live] Qwen3 Summary: {result!r}")
    print(f"[live] Summary Latency: {body['latency_ms']:.2f} ms")


@pytest.mark.skipif(not is_ollama_running(), reason="Ollama server is not active on localhost:11434")
def test_process_translate_live():
    """Test live translation endpoint against a running Ollama instance (Llama 3.2)."""
    # Clear any dependency overrides to hit the real Ollama service
    app.dependency_overrides.clear()

    req_body = {
        "transcript": (
            "Welcome to the Brief AI Integration Test. "
            "Today we will review the transcription pipeline."
        ),
        "task": "translate",
        "model": "llama3.2:1b",
        "target_language": "Spanish",
        "stream": False,
    }

    resp = client.post("/api/v1/summarization/process", json=req_body)
    assert resp.status_code == status.HTTP_200_OK
    
    body = resp.json()
    assert body["task"] == "translate"
    assert body["model"] == "llama3.2:1b"
    
    result = body["result"]
    assert len(result) > 10, f"Expected substantial translation, got: {result!r}"
    
    # Loose content-relevance check for Spanish translation keywords
    result_lower = result.lower()
    spanish_keywords = ["bienvenido", "prueba", "integración", "transcripción", "whisper", "revisar", "pipeline", "brief"]
    matched = [w for w in spanish_keywords if w in result_lower]
    assert len(matched) >= 1, f"Translation relevance check failed. Matched keywords: {matched} in result: {result!r}"
    
    # Assert token stats and latency are present
    assert isinstance(body["input_tokens"], int)
    assert body["input_tokens"] > 0
    assert isinstance(body["output_tokens"], int)
    assert body["output_tokens"] > 0
    assert isinstance(body["latency_ms"], float)
    assert body["latency_ms"] > 0.0

    print(f"\n[live] Llama 3.2 Spanish Translation: {result!r}")
    print(f"[live] Translation Latency: {body['latency_ms']:.2f} ms")


@pytest.mark.skipif(not is_ollama_running(), reason="Ollama server is not active on localhost:11434")
def test_process_action_items_live():
    """Test live action items extraction endpoint against a running Ollama instance (Qwen3)."""
    # Clear any dependency overrides to hit the real Ollama service
    app.dependency_overrides.clear()

    req_body = {
        "transcript": (
            "Welcome to the Brief AI Integration Test. "
            "Today we will review the transcription pipeline "
            "and verify that faster-whisper returns accurate results. "
            "Action item one: confirm the API is working. "
            "Action item two: proceed to the next stage."
        ),
        "task": "action_items",
        "model": "qwen3:1.7b",
        "stream": False,
    }

    resp = client.post("/api/v1/summarization/process", json=req_body)
    assert resp.status_code == status.HTTP_200_OK
    
    body = resp.json()
    assert body["task"] == "action_items"
    assert body["model"] == "qwen3:1.7b"
    
    result = body["result"]
    assert len(result) > 20, f"Expected substantial action items list, got: {result!r}"
    
    # Loose content-relevance check: must identify key concepts of action items
    result_lower = result.lower()
    relevance_keywords = ["action", "item", "confirm", "api", "working", "proceed", "stage", "task"]
    matched = [w for w in relevance_keywords if w in result_lower]
    assert len(matched) >= 2, f"Action items relevance check failed. Matched keywords: {matched} in result: {result!r}"
    
    # Assert token stats and latency are present
    assert isinstance(body["input_tokens"], int)
    assert body["input_tokens"] > 0
    assert isinstance(body["output_tokens"], int)
    assert body["output_tokens"] > 0
    assert isinstance(body["latency_ms"], float)
    assert body["latency_ms"] > 0.0

    print(f"\n[live] Qwen3 Action Items: {result!r}")
    print(f"[live] Action Items Latency: {body['latency_ms']:.2f} ms")
