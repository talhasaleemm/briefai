import pytest
import numpy as np
from unittest.mock import AsyncMock
from sqlalchemy.orm import Session
from briefai.models import User, Transcript, TranscriptChunk
from briefai.retrieval.rag_service import search, RAG_SIMILARITY_THRESHOLD

@pytest.mark.asyncio
async def test_rag_grounding_guard(db: Session):
    """
    Query with an unrelated topic and assert the system returns the 'no relevant information' message
    without invoking the LLM (i.e. search returns empty list).
    """
    user = User(email="test@test.com", username="Test", hashed_password="pw")
    db.add(user)
    db.commit()
    db.refresh(user)

    t = Transcript(user_id=user.id, title="Apples", content="I love apples")
    db.add(t)
    db.commit()
    db.refresh(t)

    # Add chunk
    chunk = TranscriptChunk(
        user_id=user.id,
        transcript_id=t.id,
        source_type="transcript",
        text_content="I love apples",
        embedding=[1.0, 0.0]
    )
    db.add(chunk)
    db.commit()

    mock_ollama = AsyncMock()
    
    # Query is unrelated (Bananas), embedding is orthogonal
    mock_ollama.embed.return_value = [0.0, 1.0]

    # Search
    results = await search("Tell me about bananas", user.id, db, mock_ollama)

    # Should return empty list because similarity is 0.0 < threshold
    assert len(results) == 0

    # Ensure it works when threshold IS met
    mock_ollama.embed.return_value = [0.6, 0.4] # dot product with [1.0, 0.0] is 0.6, normalized it's 0.6/0.72 = 0.83
    results = await search("Are apples good?", user.id, db, mock_ollama)
    assert len(results) == 1
