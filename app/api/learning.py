from fastapi import APIRouter
from pydantic import BaseModel
from typing import Dict, Any

from app.services.learning_service import record_learning_event, query_kc_retention

router = APIRouter(prefix="/api/learning", tags=["learning_auxiliary"])

class LearningEventRequest(BaseModel):
    user_id: str
    kc_id: str
    is_correct: bool

class RetentionQueryRequest(BaseModel):
    user_id: str
    kc_id: str

@router.post("/trace")
async def trace_learning_event(payload: LearningEventRequest) -> Dict[str, Any]:
    kc_state = await record_learning_event(payload.user_id, payload.kc_id, payload.is_correct)
    return {
        "status": "success",
        "message": f"Recorded event for {payload.kc_id}",
        "new_half_life_days": kc_state.current_half_life
    }

@router.get("/retention")
async def get_retention(user_id: str, kc_id: str) -> Dict[str, Any]:
    p = query_kc_retention(user_id, kc_id)
    return {
        "user_id": user_id, 
        "kc_id": kc_id, 
        "retention_probability": round(p, 4)
    }
