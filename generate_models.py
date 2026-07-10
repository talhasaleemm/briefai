import os

with open('backend/briefai/constants.py', 'w') as f:
    f.write('''from enum import Enum

class TaskType(str, Enum):
    SUMMARIZE = "summarize"
    TRANSLATE = "translate"
    ACTION_ITEMS = "action_items"
    LECTURE_NOTES = "lecture_notes"
    DECISIONS = "decisions"
    TERMINOLOGY = "terminology"

class ModelName(str, Enum):
    QWEN3 = "qwen3:1.7b"
    LLAMA32 = "llama3.2:1b"
''')

# users.py
with open('backend/briefai/models/users.py', 'w') as f:
    f.write('''from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.orm import relationship
from briefai.internal.db import Base

def utc_now() -> datetime:
    return datetime.now(timezone.utc)

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    username = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    created_at = Column(DateTime, default=utc_now, nullable=False)

    transcripts = relationship("Transcript", back_populates="user", cascade="all, delete-orphan")
    summaries = relationship("Summary", back_populates="user", cascade="all, delete-orphan")
''')

# transcripts.py
with open('backend/briefai/models/transcripts.py', 'w') as f:
    f.write('''from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, JSON
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
    diarized_segments = Column(JSON, nullable=True)

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
''')

# summaries.py
with open('backend/briefai/models/summaries.py', 'w') as f:
    f.write('''from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from briefai.internal.db import Base
from briefai.models.users import utc_now

class Summary(Base):
    __tablename__ = "summaries"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    transcript_id = Column(Integer, ForeignKey("transcripts.id", ondelete="SET NULL"), nullable=True, index=True)
    custom_template_id = Column(Integer, ForeignKey("custom_templates.id", ondelete="SET NULL"), nullable=True, index=True)
    task_type = Column(String, nullable=False)
    model = Column(String, nullable=False)
    result = Column(Text, nullable=False)
    latency_ms = Column(Integer, nullable=True)
    token_count = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=utc_now, nullable=False)

    user = relationship("User", back_populates="summaries")
    transcript = relationship("Transcript", back_populates="summaries")
    custom_template = relationship("CustomTemplate")
''')

# templates.py
with open('backend/briefai/models/templates.py', 'w') as f:
    f.write('''from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from briefai.internal.db import Base
from briefai.models.users import utc_now

class CustomTemplate(Base):
    __tablename__ = "custom_templates"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String, nullable=False)
    system_prompt = Column(Text, nullable=True)
    prompt_template = Column(Text, nullable=False)
    created_at = Column(DateTime, default=utc_now, nullable=False)

    user = relationship("User")
''')

# __init__.py
with open('backend/briefai/models/__init__.py', 'w') as f:
    f.write('''from .users import User
from .transcripts import Transcript, TranscriptChunk
from .summaries import Summary
from .templates import CustomTemplate
''')

