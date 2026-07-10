from typing import Optional
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
