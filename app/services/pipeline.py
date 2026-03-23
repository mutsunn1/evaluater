from __future__ import annotations

from typing import Dict

from app.agents.simulated_agents import (
    agent_a_roleplay,
    agent_b_time_penalized_evaluator,
    agent_c_strategy,
    agent_e_time_estimator,
)
from app.models.domain import UserState


async def start_pipeline_c_a_e(user_state: UserState) -> Dict[str, object]:
    """启动阶段 Pipeline: Agent C -> Agent A -> Agent E。"""
    strategy = await agent_c_strategy(user_state)
    question = await agent_a_roleplay(strategy["scene_guideline"], strategy["target_kcs"])
    timing = await agent_e_time_estimator(question, user_state, strategy["target_kcs"])
    return {
        "strategy": strategy,
        "question": question,
        "timing": timing,
    }


async def chat_pipeline_b_c_a_e(
    user_state: UserState,
    user_response_text: str,
    actual_time_sec: float,
) -> Dict[str, object]:
    """聊天阶段 Pipeline: Agent B -> Agent C -> (终止? 否则 Agent A -> Agent E)。"""
    evaluation = await agent_b_time_penalized_evaluator(
        user_state=user_state,
        user_response_text=user_response_text,
        actual_time_sec=actual_time_sec,
        expected_time_sec=user_state.last_expected_time_sec,
        target_kcs=user_state.last_target_kcs,
    )

    strategy = await agent_c_strategy(user_state)
    if strategy["should_stop"]:
        return {
            "evaluation": evaluation,
            "strategy": strategy,
            "completed": True,
        }

    question = await agent_a_roleplay(strategy["scene_guideline"], strategy["target_kcs"])
    timing = await agent_e_time_estimator(question, user_state, strategy["target_kcs"])
    return {
        "evaluation": evaluation,
        "strategy": strategy,
        "question": question,
        "timing": timing,
        "completed": False,
    }
