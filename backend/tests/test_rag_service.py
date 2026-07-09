import pytest
from unittest.mock import AsyncMock
from sqlalchemy.orm import Session
from app.models.database import User, Transcript, TranscriptChunk
from app.services.rag_service import _process_chunking

@pytest.mark.asyncio
async def test_rag_chunking_service(db: Session):
    """
    Verify background chunking executes and saves to the DB correctly.
    """
    user = User(email="t2@test.com", username="T2", hashed_password="pw")
    db.add(user)
    db.commit()
    db.refresh(user)

    text = "Word " * 500  # 500 words
    t = Transcript(user_id=user.id, title="Big", content=text)
    db.add(t)
    db.commit()
    db.refresh(t)

    mock_ollama = AsyncMock()
    mock_ollama.embed.return_value = [0.1] * 768

    # We process chunking synchronously for the test
    await _process_chunking(db, mock_ollama, t.id, "transcript", user.id, text, t.id)

    # 500 words with chunk_size=400, overlap=50
    # chunk 1: 0-400 (next starts at 350)
    # chunk 2: 350-750 (covers 350-500)
    # Total chunks = 2
    chunks = db.query(TranscriptChunk).filter(TranscriptChunk.transcript_id == t.id).all()
    
    assert len(chunks) == 2
    assert chunks[0].source_type == "transcript"
    assert chunks[0].user_id == user.id
    assert chunks[0].embedding == [0.1] * 768
