"""
Summarization and LLM Processing router.

Endpoints
---------
POST  /api/v1/summarization/process  — process a transcript using Ollama models
"""
from __future__ import annotations

import asyncio
import logging
import time
from typing import AsyncIterator

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from briefai.config import settings
from briefai.internal.db import get_db
from briefai.utils.deps import get_current_user
from briefai.models import User, Transcript, Summary
from briefai.schemas import SummarizationRequest, SummarizationResponse, TaskType, SummaryOut
from briefai.services.ollama_service import OllamaService, get_ollama_service
from briefai.prompts import SYSTEM_PROMPTS, TEMPLATES

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/summarization", tags=["summarization"])

# Concurrency limit for CPU-bound local models
# Lazy initialization to prevent asyncio event loop binding issues across tests/workers
_ollama_semaphore = None

def get_ollama_semaphore():
    global _ollama_semaphore
    if _ollama_semaphore is None:
        import asyncio
        _ollama_semaphore = asyncio.Semaphore(settings.OLLAMA_CONCURRENCY_LIMIT)
    return _ollama_semaphore


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
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SummarizationResponse | StreamingResponse:
    """Process a transcript with a local LLM (streaming or non-streaming) using prompt templates and system instructions."""
    # Enforce per-user transcript isolation if transcript_id is specified
    if req.transcript_id is not None:
        transcript = db.query(Transcript).filter(
            Transcript.id == req.transcript_id,
            Transcript.user_id == current_user.id
        ).first()
        if not transcript:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Transcript not found.",
            )

    prompt = ""
    system_prompt = ""
    summary_task_type = req.task.value
    
    if req.custom_template_id:
        from briefai.models import CustomTemplate
        custom_tmpl = db.query(CustomTemplate).filter(
            CustomTemplate.id == req.custom_template_id,
            CustomTemplate.user_id == current_user.id
        ).first()
        if not custom_tmpl:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Custom template not found.",
            )
        prompt = custom_tmpl.prompt_template.format(transcript=req.transcript.strip())
        system_prompt = custom_tmpl.system_prompt or "You are a helpful assistant."
        summary_task_type = f"Custom: {custom_tmpl.name}"
    else:
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
            # Safeguard: detect empty/whitespace output from Qwen3
            if not res.get("text", "").strip() and "qwen" in req.model.value.lower():
                logger.warning("Empty response detected from Qwen3. Retrying with expanded token budget (num_predict=1024)...")
                res = await svc.generate(
                    model=req.model.value,
                    prompt=prompt,
                    system_prompt=system_prompt,
                    options={"num_predict": 1024}
                )
                if not res.get("text", "").strip():
                    raise ValueError("Qwen3 failed to generate content even with expanded token budget.")
        except Exception as exc:
            logger.error("LLM generation error: %s", exc)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Ollama generation failed: {exc}",
            ) from exc

        latency_ms = (time.perf_counter() - start_time) * 1000.0
        
        # Save summary to DB
        db_summary = Summary(
            user_id=current_user.id,
            transcript_id=req.transcript_id,
            custom_template_id=req.custom_template_id,
            task_type=summary_task_type,
            model=req.model.value,
            result=res["text"],
            latency_ms=int(latency_ms),
            token_count=res.get("output_tokens") or len(res["text"].split()),
        )
        db.add(db_summary)
        db.commit()
        db.refresh(db_summary)

        # Launch async chunking for RAG
        from briefai.retrieval.rag_service import launch_chunking_task
        launch_chunking_task(db_summary.id, "summary", current_user.id, res["text"], req.transcript_id)

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
        yielded_any = False
        accumulated_text = []
        try:
            async for chunk in svc.generate_stream(
                model=req.model.value,
                prompt=prompt,
                system_prompt=system_prompt,
            ):
                text_chunk = chunk.get("text", "")
                if text_chunk:
                    yielded_any = True
                    accumulated_text.append(text_chunk)
                # Yield only text tokens in text/event-stream format
                yield text_chunk
            
            # Safeguard: detect empty stream for Qwen3
            if not yielded_any and "qwen" in req.model.value.lower():
                logger.error("Qwen3 streaming returned empty output")
                yield "\n[ERROR: Qwen3 failed to generate content due to reasoning token budget exhaustion. Please retry with a larger budget or different prompt.]"
            
            # Persist the final aggregated summary on clean completion of the stream
            if yielded_any:
                final_text = "".join(accumulated_text)
                db_summary = Summary(
                    user_id=current_user.id,
                    transcript_id=req.transcript_id,
                    custom_template_id=req.custom_template_id,
                    task_type=summary_task_type,
                    model=req.model.value,
                    result=final_text,
                    latency_ms=0,
                    token_count=len(final_text.split()),
                )
                db.add(db_summary)
                db.commit()
                db.refresh(db_summary)

                # Launch async chunking for RAG
                from briefai.retrieval.rag_service import launch_chunking_task
                launch_chunking_task(db_summary.id, "summary", current_user.id, final_text, req.transcript_id)

        except Exception as exc:
            logger.error("LLM streaming error: %s", exc)
            yield f"\n[STREAMING ERROR: {exc}]"

    return StreamingResponse(stream_generator(), media_type="text/plain")


# ── REST: Summary History ──────────────────────────────────────────────────────

@router.get(
    "/history",
    response_model=list[SummaryOut],
    summary="Get user summarization history",
)
async def get_summary_history(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[Summary]:
    """Retrieve all saved summaries and translations generated by the authenticated user."""
    return (
        db.query(Summary)
        .filter(Summary.user_id == current_user.id)
        .order_by(Summary.created_at.desc())
        .all()
    )

