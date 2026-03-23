from __future__ import annotations

import uuid
from typing import Tuple

from app.agents.simulated_agents import report_agent
from app.models.domain import AssessmentReport, KCState, UserState
from app.models.schemas import SelfAssessedLevel
from app.services.kc_catalog import KC_DEFS
from app.services.pipeline import chat_pipeline_b_c_a_e, start_pipeline_c_a_e
from app.store.memory_db import SESSIONS

INIT_MASTERY = {
    SelfAssessedLevel.BEGINNER: 0.2,
    SelfAssessedLevel.INTERMEDIATE: 0.5,
    SelfAssessedLevel.ADVANCED: 0.8,
}


def _build_initial_user_state(self_assessed_level: SelfAssessedLevel) -> UserState:
    session_id = str(uuid.uuid4())
    init_mastery = INIT_MASTERY[self_assessed_level]
    init_confidence = 0.4

    kcs = {
        item.kc_id: KCState(
            kc_id=item.kc_id,
            mastery=init_mastery,
            confidence=init_confidence,
        )
        for item in KC_DEFS
    }
    return UserState(
        session_id=session_id,
        kcs=kcs,
        global_level=self_assessed_level.value,
    )


async def start_assessment(self_assessed_level: SelfAssessedLevel) -> Tuple[UserState, str, float]:
    user_state = _build_initial_user_state(self_assessed_level)

    pipeline_result = await start_pipeline_c_a_e(user_state)
    strategy = pipeline_result["strategy"]
    question = pipeline_result["question"]
    timing = pipeline_result["timing"]

    user_state.last_question = question
    user_state.last_expected_time_sec = timing["expected_time_sec"]
    user_state.last_target_kcs = list(strategy["target_kcs"])

    SESSIONS[user_state.session_id] = user_state
    return user_state, question, timing["expected_time_sec"]


async def process_chat(session_id: str, user_response_text: str, actual_time_sec: float) -> dict:
    user_state = SESSIONS[session_id]

    pipeline_result = await chat_pipeline_b_c_a_e(user_state, user_response_text, actual_time_sec)
    strategy = pipeline_result["strategy"]
    if pipeline_result["completed"]:
        return {
            "status": "completed",
            "redirect_url": f"/api/assessment/report/{session_id}",
        }

    question = pipeline_result["question"]
    timing = pipeline_result["timing"]

    user_state.last_question = question
    user_state.last_expected_time_sec = timing["expected_time_sec"]
    user_state.last_target_kcs = list(strategy["target_kcs"])

    return {
        "status": "in_progress",
        "next_question": question,
        "expected_time_sec": timing["expected_time_sec"],
    }


async def build_report(session_id: str) -> AssessmentReport:
    user_state = SESSIONS[session_id]
    return await report_agent(user_state)
