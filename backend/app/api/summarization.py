"""
Summarization and LLM Processing router.

Endpoints
---------
POST  /api/v1/summarization/process  — process a transcript using Ollama models
"""
from __future__ import annotations

import logging
import time
from typing import AsyncIterator

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse

from app.models.schemas import SummarizationRequest, SummarizationResponse, TaskType
from app.services.ollama_service import OllamaService, get_ollama_service
from app.prompts import SYSTEM_PROMPTS, TEMPLATES

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/summarization", tags=["summarization"])


def _get_prompt_for_task(task: TaskType, transcript: str, target_language: str | None = None) -> str:
    """Helper to return formatted prompt templates for each task type using Stage 4 prompt library."""
    transcript = transcript.strip()
    template = TEMPLATES.get(task.value, "")
    if not template:
        return f"Please process the following transcript:\n\n{transcript}"

    if task == TaskType.TRANSLATE:
        lang = target_language or "English"
        return template.format(transcript=transcript, target_language=lang)

    return template.format(transcript=transcript)


@router.post(
    "/process",
    response_model=SummarizationResponse,
    summary="Process a transcript",
    description="Run summaries, translations, or extract action items from a transcript using local Qwen3 or Llama3.2 models.",
)
async def process_transcript(
    req: SummarizationRequest,
    svc: OllamaService = Depends(get_ollama_service),
) -> SummarizationResponse | StreamingResponse:
    """Process a transcript with a local LLM (streaming or non-streaming) using prompt templates and system instructions."""
    prompt = _get_prompt_for_task(req.task, req.transcript, req.target_language)
    system_prompt = SYSTEM_PROMPTS.get(req.task.value)
    
    # Non-streaming processing
    if not req.stream:
        start_time = time.perf_counter()
        try:
            res = await svc.generate(
                model=req.model.value,
                prompt=prompt,
                system_prompt=system_prompt,
            )
        except Exception as exc:
            logger.error("LLM generation error: %s", exc)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Ollama generation failed: {exc}",
            ) from exc

        latency_ms = (time.perf_counter() - start_time) * 1000.0
        return SummarizationResponse(
            task=req.task,
            model=req.model.value,
            result=res["text"],
            input_tokens=res["input_tokens"],
            output_tokens=res["output_tokens"],
            latency_ms=round(latency_ms, 2),
        )

    # Streaming response processing
    async def stream_generator() -> AsyncIterator[str]:
        try:
            async for chunk in svc.generate_stream(
                model=req.model.value,
                prompt=prompt,
                system_prompt=system_prompt,
            ):
                # Yield only text tokens in text/event-stream format
                yield chunk["text"]
        except Exception as exc:
            logger.error("LLM streaming error: %s", exc)
            yield f"\n[STREAMING ERROR: {exc}]"

    return StreamingResponse(stream_generator(), media_type="text/plain")
