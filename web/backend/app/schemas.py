from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1)


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    name: str
    created_at: datetime


class GenerationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    month: str
    source_filename: str
    status: str
    current_step: int
    error_message: str | None
    created_at: datetime
    completed_at: datetime | None
