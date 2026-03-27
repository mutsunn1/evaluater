from __future__ import annotations

import os
from typing import Dict

from app.agents.simulated_agents import (
    kc_planner_agent,
    question_selector_agent,
    state_analyzer_agent,
    time_analyzer_agent,
)
from app.models.domain import UserState


STRICT_SPEC_MODE = os.getenv("STRICT_SPEC_MODE", "1") == "1"


def _validate_start_sequence(result: Dict[str, object]) -> None:
    if not STRICT_SPEC_MODE:
        return
    required_keys = {"strategy", "question", "timing"}
    if not required_keys.issubset(result.keys()):
        raise ValueError("strict mode violation: start pipeline output is incomplete")


def _validate_chat_sequence(result: Dict[str, object]) -> None:
    if not STRICT_SPEC_MODE:
        return
    if "completed" not in result or "strategy" not in result:
        raise ValueError("strict mode violation: chat pipeline output is incomplete")
    if result.get("completed") is False:
        required_keys = {"question", "timing"}
        if not required_keys.issubset(result.keys()):
            raise ValueError("strict mode violation: in_progress response must include next question and timing")


async def main_agent_start_pipeline(user_state: UserState) -> Dict[str, object]:
    """主 Agent 启动流程：KC Planner -> Question Selector -> Time Analyzer。"""
    strategy = await kc_planner_agent(user_state)
    question = await question_selector_agent(strategy["scene_guideline"], strategy["target_kcs"])
    timing = await time_analyzer_agent(question, user_state, strategy["target_kcs"])
    result = {
        "strategy": strategy,
        "question": question,
        "timing": timing,
    }
    _validate_start_sequence(result)
    return result


async def main_agent_chat_pipeline(
    user_state: UserState,
    user_response_text: str,
    actual_time_sec: float,
) -> Dict[str, object]:
    """主 Agent 聊天流程：State Analyzer -> 终止判定 -> 继续出题。"""
    evaluation = await state_analyzer_agent(
        user_state=user_state,
        user_response_text=user_response_text,
        actual_time_sec=actual_time_sec,
        expected_time_sec=user_state.last_expected_time_sec,
        target_kcs=user_state.last_target_kcs,
    )

    strategy = await kc_planner_agent(user_state)
    if strategy["should_stop"]:
        result = {
            "evaluation": evaluation,
            "strategy": strategy,
            "completed": True,
        }
        _validate_chat_sequence(result)
        return result

    question = await question_selector_agent(strategy["scene_guideline"], strategy["target_kcs"])
    timing = await time_analyzer_agent(question, user_state, strategy["target_kcs"])
    result = {
        "evaluation": evaluation,
        "strategy": strategy,
        "question": question,
        "timing": timing,
        "completed": False,
    }
    _validate_chat_sequence(result)
    return result
