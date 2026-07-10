from datetime import datetime
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
