from typing import Optional
from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    question: str = Field(..., description="User question")
    top_k: Optional[int] = Field(default=None, ge=1, le=20)
    temperature: Optional[float] = Field(default=None, ge=0.0, le=2.0)


class HealthResponse(BaseModel):
    status: str
    index: str