"""
SQLAlchemy database models for User, Transcript, and Summary.
"""
from __future__ import annotations

from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Float, JSON
from sqlalchemy.orm import relationship

from app.core.database import Base


def utc_now() -> datetime:
    """Returns timezone-aware current UTC time."""
    return datetime.now(timezone.utc)


class User(Base):
    """User accounts table."""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    username = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    created_at = Column(DateTime, default=utc_now, nullable=False)

    # Relationships
    transcripts = relationship("Transcript", back_populates="user", cascade="all, delete-orphan")
    summaries = relationship("Summary", back_populates="user", cascade="all, delete-orphan")


class Transcript(Base):
    """Transcription documents uploaded or streamed by users."""
    __tablename__ = "transcripts"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=utc_now, nullable=False)
    diarization_status = Column(String, default="none", nullable=False)
    diarized_segments = Column(JSON, nullable=True)

    # Relationships
    user = relationship("User", back_populates="transcripts")
    summaries = relationship("Summary", back_populates="transcript", cascade="all, delete-orphan")


class CustomTemplate(Base):
    """User-defined custom prompt templates."""
    __tablename__ = "custom_templates"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String, nullable=False)
    system_prompt = Column(Text, nullable=True)
    prompt_template = Column(Text, nullable=False)
    created_at = Column(DateTime, default=utc_now, nullable=False)

    # Relationships
    user = relationship("User")


class Summary(Base):
    """Summarization and translation task records."""
    __tablename__ = "summaries"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    transcript_id = Column(Integer, ForeignKey("transcripts.id", ondelete="SET NULL"), nullable=True, index=True)
    custom_template_id = Column(Integer, ForeignKey("custom_templates.id", ondelete="SET NULL"), nullable=True, index=True)
    task_type = Column(String, nullable=False)  # e.g., summarize, translate, action_items, etc.
    model = Column(String, nullable=False)
    result = Column(Text, nullable=False)
    latency_ms = Column(Integer, nullable=True)
    token_count = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=utc_now, nullable=False)

    # Relationships
    user = relationship("User", back_populates="summaries")
    transcript = relationship("Transcript", back_populates="summaries")
    custom_template = relationship("CustomTemplate")


class TranscriptChunk(Base):
    """Chunks of transcripts/summaries embedded for RAG."""
    __tablename__ = "transcript_chunks"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    transcript_id = Column(Integer, ForeignKey("transcripts.id", ondelete="CASCADE"), nullable=True, index=True)
    source_type = Column(String, nullable=False) # 'transcript' or 'summary'
    text_content = Column(Text, nullable=False)
    embedding = Column(JSON, nullable=False) # JSON array of floats (768 dims for nomic-embed-text)
    created_at = Column(DateTime, default=utc_now, nullable=False)

    # Relationships
    user = relationship("User")
    transcript = relationship("Transcript")
