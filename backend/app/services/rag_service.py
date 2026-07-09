"""
RAG Service — handles chunking, embedding, and semantic search.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Generator

import numpy as np
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models.database import Transcript, Summary, TranscriptChunk
from app.services.ollama_service import OllamaService

logger = logging.getLogger(__name__)

# Empirical# Threshold for grounding guard
RAG_SIMILARITY_THRESHOLD = 0.45
RAG_TOP_K = 3

# Keep references to background tasks so they aren't garbage collected
_background_chunking_tasks = set()

def chunk_text(text: str, chunk_size: int = 400, overlap: int = 50) -> list[str]:
    """Simple word-based chunking with overlap."""
    words = text.split()
    chunks = []
    if not words:
        return chunks
    
    i = 0
    while i < len(words):
        chunk = " ".join(words[i:i + chunk_size])
        chunks.append(chunk)
        i += chunk_size - overlap
    return chunks


async def _process_chunking(db: Session, ollama_svc: OllamaService, entity_id: int, entity_type: str, user_id: int, text: str, transcript_id: int):
    """Core logic to chunk text, embed, and store."""
    chunks = chunk_text(text)
    
    for chunk_text_content in chunks:
        try:
            embedding = await ollama_svc.embed("nomic-embed-text", chunk_text_content)
            if not embedding:
                continue
            
            db_chunk = TranscriptChunk(
                user_id=user_id,
                transcript_id=transcript_id,
                source_type=entity_type,
                text_content=chunk_text_content,
                embedding=embedding,
            )
            db.add(db_chunk)
        except Exception as e:
            logger.error("Failed to embed chunk for %s %d: %s", entity_type, entity_id, e)
    
    db.commit()


async def _background_chunking_task(entity_id: int, entity_type: str, user_id: int, text: str, transcript_id: int):
    """Background task to chunk and embed an entity (transcript or summary)."""
    db = SessionLocal()
    ollama_svc = OllamaService()
    try:
        await _process_chunking(db, ollama_svc, entity_id, entity_type, user_id, text, transcript_id)
    except Exception as e:
        logger.error("Background chunking task failed for %s %d: %s", entity_type, entity_id, e)
    finally:
        db.close()


def launch_chunking_task(entity_id: int, entity_type: str, user_id: int, text: str, transcript_id: int):
    """Launches the chunking process without blocking."""
    task = asyncio.create_task(_background_chunking_task(entity_id, entity_type, user_id, text, transcript_id))
    _background_chunking_tasks.add(task)
    task.add_done_callback(_background_chunking_tasks.discard)


async def search(query: str, user_id: int, db: Session, ollama_svc: OllamaService) -> list[TranscriptChunk]:
    """
    Embed the query, retrieve all user chunks, compute cosine similarity via numpy,
    and return the top-K chunks above the threshold.
    """
    try:
        query_embedding = await ollama_svc.embed("nomic-embed-text", query)
    except Exception as e:
        logger.error("Failed to embed query: %s", e)
        return []

    # Strict isolation: ONLY fetch chunks for this user
    chunks = db.query(TranscriptChunk).filter(TranscriptChunk.user_id == user_id).all()
    if not chunks:
        return []

    # Compute cosine similarity using numpy
    query_vec = np.array(query_embedding, dtype=np.float32)
    
    # Ensure query vector is normalized
    q_norm = np.linalg.norm(query_vec)
    if q_norm == 0:
        return []
    query_vec = query_vec / q_norm

    scored_chunks = []
    for chunk in chunks:
        chunk_vec = np.array(chunk.embedding, dtype=np.float32)
        c_norm = np.linalg.norm(chunk_vec)
        if c_norm == 0:
            continue
        chunk_vec = chunk_vec / c_norm
        
        similarity = np.dot(query_vec, chunk_vec)
        if similarity >= RAG_SIMILARITY_THRESHOLD:
            scored_chunks.append((similarity, chunk))

    # Sort descending
    scored_chunks.sort(key=lambda x: x[0], reverse=True)
    
    # Return Top-K
    return [c for score, c in scored_chunks[:RAG_TOP_K]]
