from __future__ import annotations

import os
from typing import Any, List

from app.agents.prompts import (
    AGENT_A_PROMPT,
    AGENT_B_PROMPT,
    AGENT_C_PROMPT,
    AGENT_E_PROMPT,
    REPORT_AGENT_PROMPT,
)

try:
    from oxygent import OxyRequest, oxy
except Exception:  # pragma: no cover
    OxyRequest = Any  # type: ignore
    oxy = None  # type: ignore


async def assessment_start_workflow(oxy_request: Any) -> str:
    """OxyGent 工作流：Agent C -> Agent A -> Agent E。"""
    strategy = await oxy_request.call(
        callee="agent_c_strategy",
        arguments={"query": oxy_request.get_query(master_level=True)},
    )
    question = await oxy_request.call(
        callee="agent_a_roleplay",
        arguments={"query": strategy.output},
    )
    timing = await oxy_request.call(
        callee="agent_e_estimator",
        arguments={"query": question.output},
    )
    return f"{{\"question\": {question.output!r}, \"timing\": {timing.output!r}}}"


async def assessment_chat_workflow(oxy_request: Any) -> str:
    """OxyGent 工作流：Agent B -> Agent C -> (done?) -> Agent A -> Agent E。"""
    evaluated = await oxy_request.call(
        callee="agent_b_evaluator",
        arguments={"query": oxy_request.get_query(master_level=True)},
    )
    strategy = await oxy_request.call(
        callee="agent_c_strategy",
        arguments={"query": evaluated.output},
    )
    question = await oxy_request.call(
        callee="agent_a_roleplay",
        arguments={"query": strategy.output},
    )
    timing = await oxy_request.call(
        callee="agent_e_estimator",
        arguments={"query": question.output},
    )
    return f"{{\"evaluation\": {evaluated.output!r}, \"question\": {question.output!r}, \"timing\": {timing.output!r}}}"


def build_oxy_space(default_llm_name: str = "default_llm") -> List[Any]:
    """给出符合 OxyGent 写法的多智能体 + Workflow 组装代码。"""
    if oxy is None:
        return []

    return [
        # 1. 注册核心大模型 (使用环境变量配置)
        oxy.HttpLLM(
            name=default_llm_name,
            api_key=os.getenv("DEFAULT_LLM_API_KEY", ""),
            base_url=os.getenv("DEFAULT_LLM_BASE_URL", ""),
            model_name=os.getenv("DEFAULT_LLM_MODEL_NAME", ""),
            llm_params={"temperature": 0.3},
            semaphore=4,
            timeout=120,
        ),
        # 2. 注册各个角色 Agent
        oxy.ChatAgent(name="agent_c_strategy", prompt=AGENT_C_PROMPT, llm_model=default_llm_name),
        oxy.ChatAgent(name="agent_a_roleplay", prompt=AGENT_A_PROMPT, llm_model=default_llm_name),
        oxy.ChatAgent(name="agent_e_estimator", prompt=AGENT_E_PROMPT, llm_model=default_llm_name),
        oxy.ChatAgent(name="agent_b_evaluator", prompt=AGENT_B_PROMPT, llm_model=default_llm_name),
        oxy.ChatAgent(name="report_agent", prompt=REPORT_AGENT_PROMPT, llm_model=default_llm_name),
        oxy.WorkflowAgent(
            name="assessment_start_pipeline",
            desc="Assessment Start: C -> A -> E",
            sub_agents=["agent_c_strategy", "agent_a_roleplay", "agent_e_estimator"],
            func_workflow=assessment_start_workflow,
            llm_model=default_llm_name,
        ),
        oxy.WorkflowAgent(
            name="assessment_chat_pipeline",
            desc="Assessment Chat: B -> C -> A -> E",
            sub_agents=["agent_b_evaluator", "agent_c_strategy", "agent_a_roleplay", "agent_e_estimator"],
            func_workflow=assessment_chat_workflow,
            llm_model=default_llm_name,
        ),
        oxy.ReActAgent(
            name="assessment_master_agent",
            is_master=True,
            sub_agents=["assessment_start_pipeline", "assessment_chat_pipeline", "report_agent"],
            llm_model=default_llm_name,
        ),
    ]
