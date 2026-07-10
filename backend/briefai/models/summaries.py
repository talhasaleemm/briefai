from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
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
