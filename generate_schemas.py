# auth.py
with open('backend/briefai/schemas/auth.py', 'w') as f:
    f.write('''from datetime import datetime
from pydantic import BaseModel, Field

class UserRegister(BaseModel):
    email: str = Field(..., description="User email address")
    username: str = Field(..., min_length=3, max_length=50, description="Unique username")
    password: str = Field(..., min_length=6, description="Plaintext password")

class UserLogin(BaseModel):
    username_or_email: str = Field(..., description="Username or email address")
    password: str = Field(..., description="Plaintext password")

class UserOut(BaseModel):
    id: int
    email: str
    username: str
    created_at: datetime

    class Config:
        from_attributes = True

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"

class TokenPayload(BaseModel):
    sub: str
    type: str

UserRegister.model_rebuild()
UserLogin.model_rebuild()
UserOut.model_rebuild()
Token.model_rebuild()
TokenPayload.model_rebuild()
''')

# transcription.py
with open('backend/briefai/schemas/transcription.py', 'w') as f:
    f.write('''from typing import List, Optional
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
''')

# summarization.py
with open('backend/briefai/schemas/summarization.py', 'w') as f:
    f.write('''from typing import Optional
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
''')

# templates.py
with open('backend/briefai/schemas/templates.py', 'w') as f:
    f.write('''from typing import Optional
from datetime import datetime
from pydantic import BaseModel, Field, validator

class CustomTemplateCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    system_prompt: Optional[str] = Field(None, max_length=4000)
    prompt_template: str = Field(..., min_length=10, max_length=4000)

    @validator("prompt_template")
    def validate_template_format(cls, v):
        try:
            v.format(transcript="dummy")
        except KeyError as e:
            raise ValueError(f"Template contains unknown variable: {e}")
        except ValueError as e:
            raise ValueError(f"Template is malformed: {e}")
        
        if "{transcript}" not in v:
            raise ValueError("Template must contain the {transcript} placeholder.")
        return v

class CustomTemplateUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    system_prompt: Optional[str] = Field(None, max_length=4000)
    prompt_template: Optional[str] = Field(None, min_length=10, max_length=4000)

    @validator("prompt_template")
    def validate_template_format(cls, v):
        if v is None:
            return v
        try:
            v.format(transcript="dummy")
        except KeyError as e:
            raise ValueError(f"Template contains unknown variable: {e}")
        except ValueError as e:
            raise ValueError(f"Template is malformed: {e}")
        
        if "{transcript}" not in v:
            raise ValueError("Template must contain the {transcript} placeholder.")
        return v

class CustomTemplateOut(BaseModel):
    id: int
    user_id: int
    name: str
    system_prompt: Optional[str]
    prompt_template: str
    created_at: datetime

    class Config:
        from_attributes = True

CustomTemplateOut.model_rebuild()
''')

# __init__.py
with open('backend/briefai/schemas/__init__.py', 'w') as f:
    f.write('''from .auth import UserRegister, UserLogin, UserOut, Token, TokenPayload
from .transcription import TranscriptSegment, LabeledSegment, TranscriptionResult, TranscriptOut
from .summarization import SummarizationRequest, SummarizationResponse, SummaryOut, BenchmarkResult
from .templates import CustomTemplateCreate, CustomTemplateUpdate, CustomTemplateOut
''')

