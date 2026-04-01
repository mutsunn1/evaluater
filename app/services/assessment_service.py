from __future__ import annotations

import uuid
from typing import Tuple

from app.agents.oxygent_workflows import report_agent
from app.models.domain import AssessmentReport, KCState, UserState
from app.models.schemas import SelfAssessedLevel
from app.services.kc_catalog import KC_DEFS, build_initial_dag_state, build_level_seed
from app.services.knowledge_state import seed_alpha_beta
from app.services.pipeline import main_agent_chat_pipeline, main_agent_start_pipeline
from app.store.memory_db import SESSIONS


def _build_initial_user_state(user_id: str, self_assessed_level: SelfAssessedLevel) -> UserState:
    session_id = str(uuid.uuid4())
    init_mastery, init_confidence, vocab_bucket, target_tier = build_level_seed(self_assessed_level.value)

    alpha_seed, beta_seed = seed_alpha_beta(init_mastery, init_confidence)
    kcs = {
        item.kc_id: KCState(
            kc_id=item.kc_id,
            alpha=alpha_seed,
            beta=beta_seed,
            mastery=init_mastery,
            confidence=init_confidence,
        )
        for item in KC_DEFS
    }

    dag_state = build_initial_dag_state()
    dag_state["target_tier"] = target_tier

    return UserState(
        session_id=session_id,
        user_id=user_id,
        kcs=kcs,
        vocab_bucket=vocab_bucket,
        dag_state=dag_state,
        global_level=self_assessed_level.value,
    )


async def start_assessment(user_id: str, self_assessed_level: SelfAssessedLevel) -> Tuple[UserState, str, float]:
    user_state = _build_initial_user_state(user_id=user_id, self_assessed_level=self_assessed_level)

    pipeline_result = await main_agent_start_pipeline(user_state)
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

    pipeline_result = await main_agent_chat_pipeline(user_state, user_response_text, actual_time_sec)
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
