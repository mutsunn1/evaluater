from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.models.schemas import (
    ChatRequest,
    ChatResponse,
    StartAssessmentRequest,
    StartAssessmentResponse,
)
from app.models.domain import AssessmentReport
from app.services.assessment_service import build_report, process_chat, start_assessment
from app.store.memory_db import SESSIONS

router = APIRouter(prefix="/api/assessment", tags=["assessment"])


@router.post("/start", response_model=StartAssessmentResponse)
async def start_assessment_api(payload: StartAssessmentRequest) -> StartAssessmentResponse:
    user_state, first_question, expected_time = await start_assessment(
        user_id=payload.user_id,
        self_assessed_level=payload.self_assessed_level,
    )
    return StartAssessmentResponse(
        session_id=user_state.session_id,
        first_question=first_question,
        expected_time_sec=expected_time,
    )


@router.post("/chat", response_model=ChatResponse, response_model_exclude_none=True)
async def assessment_chat_api(payload: ChatRequest) -> ChatResponse:
    if payload.session_id not in SESSIONS:
        raise HTTPException(status_code=404, detail="session_id not found")

    result = await process_chat(
        session_id=payload.session_id,
        user_response_text=payload.user_response_text,
        actual_time_sec=payload.actual_time_sec,
    )
    return ChatResponse(**result)


@router.get("/report/{session_id}", response_model=AssessmentReport)
async def assessment_report_api(session_id: str):
    if session_id not in SESSIONS:
        raise HTTPException(status_code=404, detail="session_id not found")

    report = await build_report(session_id)
    return report
