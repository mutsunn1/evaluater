from __future__ import annotations

from typing import Dict, List

from pydantic import BaseModel, Field


class KCState(BaseModel):
    kc_id: str
    mastery: float = Field(ge=0.0, le=1.0)
    confidence: float = Field(ge=0.0, le=1.0)


class CognitiveFluency(BaseModel):
    avg_time_ratio: float = Field(ge=0.0)
    fluency_label: str
    interpretation: str


class DetailedUserProfile(BaseModel):
    radar_chart: Dict[str, float]
    cognitive_fluency: CognitiveFluency
    strengths: List[str]
    weaknesses: List[str]


class AssessmentReport(BaseModel):
    estimated_hsk_level: str
    detailed_user_profile: DetailedUserProfile


class UserState(BaseModel):
    session_id: str
    kcs: Dict[str, KCState]
    global_level: str
    rounds: int = 0
    total_actual_time_sec: float = 0.0
    total_expected_time_sec: float = 0.0
    last_question: str = ""
    last_expected_time_sec: float = 12.0
    last_target_kcs: List[str] = Field(default_factory=list)
    conversation_history: List[Dict[str, str]] = Field(default_factory=list)
