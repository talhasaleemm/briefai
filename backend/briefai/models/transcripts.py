from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship
from briefai.internal.db import Base
from briefai.models.users import utc_now

class Transcript(Base):
    __tablename__ = "transcripts"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=utc_now, nullable=False)
    diarization_status = Column(String, default="none", nullable=False)
    diarized_segments = Column(JSON, nullable=False, default=list, server_default='[]')

    user = relationship("User", back_populates="transcripts")
    summaries = relationship("Summary", back_populates="transcript", cascade="all, delete-orphan")

class TranscriptChunk(Base):
    __tablename__ = "transcript_chunks"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    transcript_id = Column(Integer, ForeignKey("transcripts.id", ondelete="CASCADE"), nullable=True, index=True)
    source_type = Column(String, nullable=False)
    text_content = Column(Text, nullable=False)
    embedding = Column(JSON, nullable=False)
    created_at = Column(DateTime, default=utc_now, nullable=False)

    user = relationship("User")
    transcript = relationship("Transcript")
