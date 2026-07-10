import pytest
import numpy as np
from unittest.mock import AsyncMock
from sqlalchemy.orm import Session
from briefai.models import User, Transcript, TranscriptChunk
from briefai.retrieval.rag_service import search

@pytest.mark.asyncio
async def test_rag_isolation(db: Session):
    """
    Register two users with different transcripts. Confirm User A's chat queries
    NEVER surface User B's chunks, proving strict DB isolation.
    """
    # Create User A and B
    user_a = User(email="a@test.com", username="UserA", hashed_password="pw")
    user_b = User(email="b@test.com", username="UserB", hashed_password="pw")
    db.add_all([user_a, user_b])
    db.commit()
    db.refresh(user_a)
    db.refresh(user_b)

    # Create transcripts
    t_a = Transcript(user_id=user_a.id, title="Apples", content="I love apples")
    t_b = Transcript(user_id=user_b.id, title="Bananas", content="I love bananas")
    db.add_all([t_a, t_b])
    db.commit()
    db.refresh(t_a)
    db.refresh(t_b)

    # Create chunks for both users with fake embeddings
    # Apples embedding
    chunk_a = TranscriptChunk(
        user_id=user_a.id,
        transcript_id=t_a.id,
        source_type="transcript",
        text_content="I love apples",
        embedding=[1.0, 0.0]
    )
    # Bananas embedding
    chunk_b = TranscriptChunk(
        user_id=user_b.id,
        transcript_id=t_b.id,
        source_type="transcript",
        text_content="I love bananas",
        embedding=[0.0, 1.0]
    )
    db.add_all([chunk_a, chunk_b])
    db.commit()

    # Mock OllamaService
    mock_ollama = AsyncMock()
    
    # Query from User A that matches User B's embedding perfectly!
    mock_ollama.embed.return_value = [0.0, 1.0]  # This matches Bananas!

    # Search for User A
    results = await search("Tell me about bananas", user_a.id, db, mock_ollama)

    # User A should NEVER see User B's chunk, even if the similarity is 1.0
    # User A's chunk has similarity 0.0 with [0.0, 1.0], so it falls below threshold
    assert len(results) == 0

    # Let's verify User A CAN retrieve their own chunk if it matches
    mock_ollama.embed.return_value = [1.0, 0.0]  # Matches Apples
    results = await search("Tell me about apples", user_a.id, db, mock_ollama)
    assert len(results) == 1
    assert results[0].text_content == "I love apples"
    assert results[0].user_id == user_a.id
