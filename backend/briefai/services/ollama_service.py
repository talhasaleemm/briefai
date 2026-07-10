"""
OllamaService — handles communication with the local Ollama LLM instance (Qwen3 & Llama3.2).
Uses httpx for asynchronous HTTP calls to Ollama REST APIs.
"""
from __future__ import annotations

import json
import logging
import asyncio
from typing import Any, AsyncIterator, Optional

import httpx
from briefai.config import settings

logger = logging.getLogger(__name__)

# Global semaphore to limit concurrent requests to Ollama
# Lazy initialization to prevent asyncio event loop binding issues across tests/workers
_ollama_semaphore = None

def get_ollama_semaphore():
    global _ollama_semaphore
    if _ollama_semaphore is None:
        _ollama_semaphore = asyncio.Semaphore(settings.OLLAMA_CONCURRENCY_LIMIT)
    return _ollama_semaphore

class OllamaService:
    """Wraps Ollama local REST API for model inference."""

    def __init__(self, base_url: Optional[str] = None) -> None:
        self.base_url = (base_url or settings.OLLAMA_BASE_URL).rstrip("/")
        self.timeout = settings.OLLAMA_TIMEOUT

    async def embed(self, model: str, prompt: str) -> list[float]:
        """
        Call Ollama /api/embeddings asynchronously.
        Must acquire the global ollama_semaphore to prevent resource contention.
        """
        url = f"{self.base_url}/api/embeddings"
        payload = {"model": model, "prompt": prompt}

        logger.info("Ollama embedding request to %s (model=%s)", url, model)
        async with get_ollama_semaphore():
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                try:
                    response = await client.post(url, json=payload)
                    response.raise_for_status()
                    data = response.json()
                    return data.get("embedding", [])
                except httpx.HTTPError as exc:
                    logger.error("Ollama embedding HTTP request failed: %s", exc)
                    raise RuntimeError(f"Ollama embedding failed: {exc}") from exc

    async def generate(
        self,
        model: str,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.0,
        options: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """
        Call Ollama /api/generate asynchronously (non-streaming).
        Returns a dict containing response text, token counts, and latency.
        """
        url = f"{self.base_url}/api/generate"
        payload = self._build_payload(model, prompt, system_prompt, False, temperature, options)

        logger.info("Ollama request to %s (model=%s)", url, model)
        async with get_ollama_semaphore():
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                try:
                    response = await client.post(url, json=payload)
                    response.raise_for_status()
                    data = response.json()
                    return {
                        "text": data.get("response", "").strip(),
                        "input_tokens": data.get("prompt_eval_count"),
                        "output_tokens": data.get("eval_count"),
                        "duration_ns": data.get("total_duration"),
                    }
                except httpx.HTTPError as exc:
                    logger.error("Ollama HTTP request failed: %s", exc)
                    raise RuntimeError(f"Ollama connection failed: {exc}") from exc

    async def generate_stream(
        self,
        model: str,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.0,
        options: Optional[dict[str, Any]] = None,
    ) -> AsyncIterator[dict[str, Any]]:
        """
        Call Ollama /api/generate asynchronously, yielding JSON chunks for streaming responses.
        """
        url = f"{self.base_url}/api/generate"
        payload = self._build_payload(model, prompt, system_prompt, True, temperature, options)

        logger.info("Ollama streaming request to %s (model=%s)", url, model)
        async with get_ollama_semaphore():
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                try:
                    async with client.stream("POST", url, json=payload) as response:
                        response.raise_for_status()
                        async for line in response.aiter_lines():
                            if not line.strip():
                                continue
                            data = json.loads(line)
                            yield {
                                "text": data.get("response", ""),
                                "done": data.get("done", False),
                                "input_tokens": data.get("prompt_eval_count") if data.get("done") else None,
                                "output_tokens": data.get("eval_count") if data.get("done") else None,
                                "duration_ns": data.get("total_duration") if data.get("done") else None,
                            }
                except httpx.HTTPError as exc:
                    logger.error("Ollama HTTP streaming failed: %s", exc)
                    raise RuntimeError(f"Ollama streaming connection failed: {exc}") from exc

    def _build_payload(
        self,
        model: str,
        prompt: str,
        system_prompt: Optional[str],
        stream: bool,
        temperature: float,
        extra_options: Optional[dict[str, Any]],
    ) -> dict[str, Any]:
        """Construct the standard Ollama request payload."""
        options = {"temperature": temperature}
        if extra_options:
            options.update(extra_options)

        payload = {
            "model": model,
            "prompt": prompt,
            "stream": stream,
            "options": options,
        }
        if system_prompt:
            payload["system"] = system_prompt
        return payload


# Dependency provider
def get_ollama_service() -> OllamaService:
    """FastAPI Dependency injection provider for OllamaService."""
    return OllamaService()
