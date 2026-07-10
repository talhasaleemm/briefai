"""
Chat and RAG API router.
"""
from __future__ import annotations

import logging
from typing import AsyncIterator

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from briefai.internal.db import get_db
from briefai.utils.deps import get_current_user
from briefai.models import User
from briefai.services.ollama_service import OllamaService, get_ollama_service
from briefai.retrieval.rag_service import search

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat", tags=["chat"])

class ChatRequest(BaseModel):
    query: str
    model: str = "llama3.2:1b"

@router.post(
    "/ask",
    summary="Ask BriefAI via RAG",
    description="Ask a question over the user's meeting history.",
)
async def ask_briefai(
    req: ChatRequest,
    svc: OllamaService = Depends(get_ollama_service),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = req.query.strip()
    if not query:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Query cannot be empty.")

    # 1. Retrieve relevant chunks
    chunks = await search(query, current_user.id, db, svc)
    
    # 2. Hallucination Guard / Zero-State Check
    if not chunks:
        # Check if user has ANY chunks to differentiate Zero-State from No Match
        from briefai.models import TranscriptChunk
        has_history = db.query(TranscriptChunk).filter(TranscriptChunk.user_id == current_user.id).first() is not None
        
        message = "No relevant information found in your history." if has_history else "You have no meeting history yet. Upload or record a meeting to start asking questions."
        
        async def fast_fail_stream():
            yield message
        return StreamingResponse(fast_fail_stream(), media_type="text/plain")

    # 3. Build Prompt
    context_text = "\n\n".join([f"[{c.source_type.upper()}] {c.text_content}" for c in chunks])
    system_prompt = (
        "You are BriefAI, an intelligent assistant. Answer the user's question based strictly on the provided Context from their past meetings. "
        "If the answer is not contained in the Context, say 'I cannot find the answer in your meeting history.' Do not hallucinate external facts."
    )
    full_prompt = f"Context:\n{context_text}\n\nQuestion: {query}"

    # 4. Stream Response
    async def stream_generator() -> AsyncIterator[str]:
        try:
            async for chunk in svc.generate_stream(
                model=req.model,
                prompt=full_prompt,
                system_prompt=system_prompt,
            ):
                text_chunk = chunk.get("text", "")
                if text_chunk:
                    yield text_chunk
        except Exception as exc:
            logger.error("RAG LLM streaming error: %s", exc)
            yield f"\n[STREAMING ERROR: {exc}]"

    return StreamingResponse(stream_generator(), media_type="text/plain")
