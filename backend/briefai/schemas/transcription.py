from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel, Field

class TranscriptSegment(BaseModel):
    start: float = Field(..., description="Segment start time in seconds")
    end: float = Field(..., description="Segment end time in seconds")
    text: str = Field(..., description="Transcribed text for this segment")
    confidence: Optional[float] = Field(None, description="Avg log-prob confidence score")

class LabeledSegment(TranscriptSegment):
    speaker: str = Field(..., description="Assigned speaker label (e.g. 'Speaker 1')")

class TranscriptionResult(BaseModel):
    id: Optional[int] = Field(None, description="Database ID of the persisted transcript")
    transcript: str = Field(..., description="Full concatenated transcript")
    segments: List[TranscriptSegment] = Field(default_factory=list)
    language: str = Field(..., description="Detected language code")
    duration_seconds: float = Field(..., description="Total audio duration")
    diarization_status: str = Field("none", description="'none', 'pending', 'complete', or 'failed'")
    diarized_segments: List[LabeledSegment] = Field(default_factory=list)

class TranscriptOut(BaseModel):
    id: int
    title: str
    content: str
    created_at: datetime
    diarization_status: str = "none"
    diarized_segments: List[LabeledSegment] = Field(default_factory=list)

    class Config:
        from_attributes = True

TranscriptOut.model_rebuild()
