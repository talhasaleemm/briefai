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

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/summarization", tags=["summarization"])


def _get_prompt_for_task(task: TaskType, transcript: str, target_language: str | None = None) -> str:
    """Helper to return simple prompt templates for each task type (Stage 3 placeholders)."""
    transcript = transcript.strip()
    if task == TaskType.SUMMARIZE:
        return f"Please provide a concise summary of the following meeting transcript:\n\n{transcript}"
    elif task == TaskType.TRANSLATE:
        lang = target_language or "English"
        return f"Please translate the following meeting transcript to {lang}:\n\n{transcript}"
    elif task == TaskType.ACTION_ITEMS:
        return f"Please list all action items, assignees, and tasks identified in the following meeting transcript:\n\n{transcript}"
    elif task == TaskType.LECTURE_NOTES:
        return f"Please compile the following transcript into structured, detailed study/lecture notes:\n\n{transcript}"
    elif task == TaskType.DECISIONS:
        return f"Please extract all key decisions made in the following meeting transcript:\n\n{transcript}"
    elif task == TaskType.TERMINOLOGY:
        return f"Please extract and define key terms, acronyms, and technical terminology from the following transcript:\n\n{transcript}"
    return f"Please process the following transcript:\n\n{transcript}"


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
    """Process a transcript with a local LLM (streaming or non-streaming)."""
    prompt = _get_prompt_for_task(req.task, req.transcript, req.target_language)
    
    # Non-streaming processing
    if not req.stream:
        start_time = time.perf_counter()
        try:
            res = await svc.generate(model=req.model.value, prompt=prompt)
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
            async for chunk in svc.generate_stream(model=req.model.value, prompt=prompt):
                # Yield only text tokens in text/event-stream format
                yield chunk["text"]
        except Exception as exc:
            logger.error("LLM streaming error: %s", exc)
            yield f"\n[STREAMING ERROR: {exc}]"

    return StreamingResponse(stream_generator(), media_type="text/plain")
