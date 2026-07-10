from typing import Optional
from datetime import datetime
from pydantic import BaseModel, Field
from briefai.constants import TaskType, ModelName

class SummarizationRequest(BaseModel):
    transcript: str = Field(..., min_length=10, description="Input transcript text")
    transcript_id: Optional[int] = Field(None, description="Optional DB ID of the transcript to reference")
    custom_template_id: Optional[int] = Field(None, description="Optional ID of a CustomTemplate to use instead of task")
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

class SummaryOut(BaseModel):
    id: int
    transcript_id: Optional[int]
    task_type: TaskType
    model: str
    result: str
    latency_ms: Optional[int]
    token_count: Optional[int]
    created_at: datetime

    class Config:
        from_attributes = True

class BenchmarkResult(BaseModel):
    model: str
    task: TaskType
    latency_ms: float
    tokens_per_second: float
    memory_mb: float
    input_tokens: int
    output_tokens: int
    quality_note: Optional[str] = None

SummaryOut.model_rebuild()
