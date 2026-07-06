"""Pydantic schemas for BriefAI API request/response models."""
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


# ── Enums ─────────────────────────────────────────────────────────────────────

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


# ── Transcription ──────────────────────────────────────────────────────────────

class TranscriptSegment(BaseModel):
    start: float = Field(..., description="Segment start time in seconds")
    end: float = Field(..., description="Segment end time in seconds")
    text: str = Field(..., description="Transcribed text for this segment")
    confidence: Optional[float] = Field(None, description="Avg log-prob confidence score")


class TranscriptionResult(BaseModel):
    transcript: str = Field(..., description="Full concatenated transcript")
    segments: List[TranscriptSegment] = Field(default_factory=list)
    language: str = Field(..., description="Detected language code")
    duration_seconds: float = Field(..., description="Total audio duration")


# ── LLM / Summarization ───────────────────────────────────────────────────────

class SummarizationRequest(BaseModel):
    transcript: str = Field(..., min_length=10, description="Input transcript text")
    task: TaskType = Field(TaskType.SUMMARIZE, description="Processing task to perform")
    model: ModelName = Field(ModelName.QWEN3, description="Ollama model to use")
    target_language: Optional[str] = Field(
        None, description="Target language for translation tasks (e.g. 'French', 'Arabic')"
    )
    stream: bool = Field(False, description="Stream the LLM response token by token")


class SummarizationResponse(BaseModel):
    task: TaskType
    model: str
    result: str = Field(..., description="Processed LLM output")
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    latency_ms: Optional[float] = None


# ── Benchmarking ──────────────────────────────────────────────────────────────

class BenchmarkResult(BaseModel):
    model: str
    task: TaskType
    latency_ms: float
    tokens_per_second: float
    memory_mb: float
    input_tokens: int
    output_tokens: int
    quality_note: Optional[str] = None
