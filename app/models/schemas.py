from __future__ import annotations

from enum import Enum
from typing import Literal, Optional

from pydantic import BaseModel, Field


class SelfAssessedLevel(str, Enum):
    BEGINNER = "BEGINNER"
    INTERMEDIATE = "INTERMEDIATE"
    ADVANCED = "ADVANCED"


class StartAssessmentRequest(BaseModel):
    user_id: str = Field(min_length=1)
    self_assessed_level: SelfAssessedLevel


class StartAssessmentResponse(BaseModel):
    session_id: str
    first_question: str
    expected_time_sec: float


class ChatRequest(BaseModel):
    session_id: str
    user_response_text: str = Field(min_length=1)
    actual_time_sec: float = Field(gt=0)


class ChatResponse(BaseModel):
    status: Literal["in_progress", "completed"]
    session_id: Optional[str] = None
    next_question: Optional[str] = None
    expected_time_sec: Optional[float] = None
    redirect_url: Optional[str] = None
