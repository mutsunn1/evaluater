from __future__ import annotations

import asyncio
import json
import os
from typing import Any, Dict, List, Optional

from app.agents.prompts import (
    AGENT_A_PROMPT,
    AGENT_B_PROMPT,
    AGENT_C_PROMPT,
    AGENT_E_PROMPT,
    AGENT_F_PROMPT,
    REPORT_AGENT_PROMPT,
)
from app.models.domain import AssessmentReport, TurnTrace, UserState
from app.services.kc_catalog import KC_BY_ID
from app.services.knowledge_state import (
    dag_reverse_propagate,
    time_decay_gamma,
    update_kc_with_bkt,
)

try:
    from oxygent import MAS, OxyRequest, oxy
except Exception:  # pragma: no cover
    MAS = Any  # type: ignore
    OxyRequest = Any  # type: ignore
    oxy = None  # type: ignore


_MAS_INSTANCE: Optional[Any] = None
_MAS_LOCK = asyncio.Lock()


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


def _extract_json_text(raw: str) -> str:
    text = raw.strip()
    if text.startswith("```"):
        lines = [line for line in text.splitlines() if not line.strip().startswith("```")]
        text = "\n".join(lines).strip()

    if text.startswith("{") and text.endswith("}"):
        return text

    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or start >= end:
        raise ValueError("No JSON object found in oxygent response")
    return text[start : end + 1]


def _parse_json_object(raw: Any) -> Dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    if raw is None:
        raise ValueError("oxygent response is empty")

    text = str(raw)
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        parsed = json.loads(_extract_json_text(text))
    if not isinstance(parsed, dict):
        raise ValueError("oxygent response json must be an object")
    return parsed


async def _ensure_mas() -> Any:
    global _MAS_INSTANCE
    if _MAS_INSTANCE is not None:
        return _MAS_INSTANCE

    async with _MAS_LOCK:
        if _MAS_INSTANCE is not None:
            return _MAS_INSTANCE

        if oxy is None:
            raise RuntimeError("oxygent is not available")
        if not os.getenv("DEFAULT_LLM_API_KEY", "").strip():
            raise RuntimeError("DEFAULT_LLM_API_KEY is required")
        if not os.getenv("DEFAULT_LLM_MODEL_NAME", "").strip():
            raise RuntimeError("DEFAULT_LLM_MODEL_NAME is required")

        _MAS_INSTANCE = await MAS.create(name="assessment_mas", oxy_space=build_oxy_space())
        return _MAS_INSTANCE


async def _call_agent(callee: str, query: str) -> Any:
    mas = await _ensure_mas()
    response = await mas.call(callee=callee, arguments={"query": query})
    if getattr(response, "state", None) is None:
        raise RuntimeError(f"oxygent call failed: {callee}")
    return response.output


def _state_compact(user_state: UserState, top_n: int = 10) -> Dict[str, object]:
    ranked = sorted(
        user_state.kcs.values(),
        key=lambda x: (x.confidence, x.mastery),
    )
    return {
        "global_level": user_state.global_level,
        "rounds": user_state.rounds,
        "max_rounds": user_state.max_rounds,
        "target_tier": user_state.dag_state.get("target_tier", 2),
        "kcs_low_conf": [
            {
                "kc_id": item.kc_id,
                "alpha": round(item.alpha, 4),
                "beta": round(item.beta, 4),
                "mastery": round(item.mastery, 4),
                "confidence": round(item.confidence, 4),
                "tier": KC_BY_ID[item.kc_id].tier if item.kc_id in KC_BY_ID else None,
                "description": KC_BY_ID[item.kc_id].description if item.kc_id in KC_BY_ID else "",
            }
            for item in ranked[:top_n]
        ],
        "last_target_kcs": list(user_state.last_target_kcs),
        "last_expected_time_sec": user_state.last_expected_time_sec,
        "vocab_bucket": sorted(list(user_state.vocab_bucket))[:50],
    }


async def assessment_start_workflow(oxy_request: Any) -> str:
    """OxyGent 工作流：KC Planner -> Question Selector -> Time Analyzer。"""
    strategy = await oxy_request.call(
        callee="kc_planner",
        arguments={"query": oxy_request.get_query(master_level=True)},
    )
    question = await oxy_request.call(
        callee="question_selector",
        arguments={"query": strategy.output},
    )
    timing = await oxy_request.call(
        callee="time_analyzer",
        arguments={"query": question.output},
    )
    return f"{{\"question\": {question.output!r}, \"timing\": {timing.output!r}}}"


async def assessment_chat_workflow(oxy_request: Any) -> str:
    """OxyGent 工作流：State Analyzer -> KC Planner -> Question Selector -> Time Analyzer。"""
    evaluated = await oxy_request.call(
        callee="state_analyzer",
        arguments={"query": oxy_request.get_query(master_level=True)},
    )
    strategy = await oxy_request.call(
        callee="kc_planner",
        arguments={"query": evaluated.output},
    )
    question = await oxy_request.call(
        callee="question_selector",
        arguments={"query": strategy.output},
    )
    timing = await oxy_request.call(
        callee="time_analyzer",
        arguments={"query": question.output},
    )
    return f"{{\"evaluation\": {evaluated.output!r}, \"question\": {question.output!r}, \"timing\": {timing.output!r}}}"


def build_oxy_space(default_llm_name: str = "default_llm") -> List[Any]:
    """给出符合 OxyGent 写法的多智能体 + Workflow 组装代码。

    说明：当前项目默认使用真实 API Key 驱动的 LLM Agent；
    此函数提供 OxyGent 的标准装配方式。
    """
    if oxy is None:
        return []

    return [
        # 1. 注册核心大模型 (使用环境变量配置)
        oxy.HttpLLM(
            name=default_llm_name,
            api_key=os.getenv("DEFAULT_LLM_API_KEY", ""),
            base_url=os.getenv("DEFAULT_LLM_BASE_URL", "https://api.openai.com/v1"),
            model_name=os.getenv("DEFAULT_LLM_MODEL_NAME", ""),
            llm_params={"temperature": 0.3},
            semaphore=4,
            timeout=120,
        ),
        # 2. 注册角色 Agent
        oxy.ChatAgent(name="kc_planner", prompt=AGENT_C_PROMPT, llm_model=default_llm_name),
        oxy.ChatAgent(name="question_selector", prompt=AGENT_A_PROMPT, llm_model=default_llm_name),
        oxy.ChatAgent(name="time_analyzer", prompt=AGENT_E_PROMPT, llm_model=default_llm_name),
        oxy.ChatAgent(name="state_analyzer", prompt=AGENT_B_PROMPT, llm_model=default_llm_name),
        oxy.ChatAgent(name="report_agent", prompt=REPORT_AGENT_PROMPT, llm_model=default_llm_name),
        oxy.ChatAgent(name="agent_f_feature", prompt=AGENT_F_PROMPT, llm_model=default_llm_name),
        # 3. 注册工作流 Agent
        oxy.WorkflowAgent(
            name="assessment_start_pipeline",
            desc="Assessment Start: KC Planner -> Question Selector -> Time Analyzer",
            sub_agents=["kc_planner", "question_selector", "time_analyzer"],
            func_workflow=assessment_start_workflow,
            llm_model=default_llm_name,
        ),
        oxy.WorkflowAgent(
            name="assessment_chat_pipeline",
            desc="Assessment Chat: State Analyzer -> KC Planner -> Question Selector -> Time Analyzer",
            sub_agents=["state_analyzer", "kc_planner", "question_selector", "time_analyzer"],
            func_workflow=assessment_chat_workflow,
            llm_model=default_llm_name,
        ),
        # 4. 主 Agent 负责路由总控
        oxy.ReActAgent(
            name="assessment_master_agent",
            is_master=True,
            sub_agents=["assessment_start_pipeline", "assessment_chat_pipeline", "report_agent"],
            llm_model=default_llm_name,
        ),
    ]


async def kc_planner_agent(user_state: UserState) -> Dict[str, object]:
    query = (
        "请基于以下状态规划下一轮目标。"
        "必须输出 JSON，字段包含 target_kcs(list)、scene_guideline(str)、should_stop(bool)、reason(str)。"
        f"状态数据: {_state_compact(user_state)}"
    )
    payload = _parse_json_object(await _call_agent("kc_planner", query))

    target_kcs = payload.get("target_kcs")
    if not isinstance(target_kcs, list):
        raise ValueError("kc_planner response missing target_kcs list")
    cleaned = [kc for kc in target_kcs if isinstance(kc, str) and kc in user_state.kcs]
    if not cleaned:
        raise ValueError("kc_planner returned no valid target_kcs")

    scene_guideline = payload.get("scene_guideline")
    should_stop = payload.get("should_stop")
    reason = payload.get("reason")

    if not isinstance(scene_guideline, str) or not scene_guideline.strip():
        raise ValueError("kc_planner response missing scene_guideline")
    if not isinstance(should_stop, bool):
        raise ValueError("kc_planner response should_stop must be bool")

    return {
        "target_kcs": cleaned[:2],
        "scene_guideline": scene_guideline.strip(),
        "should_stop": should_stop,
        "reason": reason if isinstance(reason, str) else "llm_reason_not_provided",
    }


async def question_selector_agent(scene_guideline: str, target_kcs: List[str]) -> str:
    query = (
        "请生成一句自然中文提问，不要输出解释。"
        f"scene_guideline: {scene_guideline}\n"
        f"target_kcs: {target_kcs}"
    )
    output = await _call_agent("question_selector", query)
    question = str(output).strip().replace("\n", " ")
    if not question:
        raise ValueError("question_selector returned empty question")
    return question


async def time_analyzer_agent(question: str, user_state: UserState, target_kcs: List[str]) -> Dict[str, float]:
    query = (
        "请估计以下题目的 expected_time_sec。仅输出 JSON。"
        f"question: {question}\n"
        f"target_kcs: {target_kcs}\n"
        f"state: {_state_compact(user_state, top_n=6)}"
    )
    payload = _parse_json_object(await _call_agent("time_analyzer", query))

    def as_float(name: str) -> float:
        value = payload.get(name)
        if isinstance(value, (int, float)):
            return round(float(value), 2)
        raise ValueError(f"time_analyzer missing numeric field: {name}")

    return {
        "expected_time_sec": max(1.0, as_float("expected_time_sec")),
        "t_perception": max(0.0, as_float("t_perception")),
        "t_retrieval": max(0.0, as_float("t_retrieval")),
        "complexity_bonus": max(0.0, as_float("complexity_bonus")),
    }


async def state_analyzer_agent(
    user_state: UserState,
    user_response_text: str,
    actual_time_sec: float,
    expected_time_sec: float,
    target_kcs: List[str],
) -> Dict[str, object]:
    if not target_kcs:
        target_kcs = sorted(user_state.kcs.keys(), key=lambda k: user_state.kcs[k].confidence)[:1]

    query = (
        "请评估回答正确性并输出 JSON: {correctness: 0~1, bucket: correct_fast/correct_slow/wrong, reason: str}。"
        f"question: {user_state.last_question}\n"
        f"answer: {user_response_text}\n"
        f"target_kcs: {target_kcs}\n"
        f"actual_time_sec: {actual_time_sec}\n"
        f"expected_time_sec: {expected_time_sec}"
    )
    payload = _parse_json_object(await _call_agent("state_analyzer", query))

    correctness_raw = payload.get("correctness")
    correctness = _clamp01(float(correctness_raw)) if isinstance(correctness_raw, (int, float)) else 0.0
    time_ratio = actual_time_sec / max(0.1, expected_time_sec)
    gamma = time_decay_gamma(actual_time_sec=actual_time_sec, expected_time_sec=expected_time_sec)

    bucket = payload.get("bucket")
    if not isinstance(bucket, str):
        if correctness >= 0.6 and actual_time_sec < expected_time_sec:
            bucket = "correct_fast"
        elif correctness >= 0.6:
            bucket = "correct_slow"
        else:
            bucket = "wrong"

    if bucket == "correct_fast":
        mastery_delta = 0.12
        confidence_delta = 0.10
    elif bucket == "correct_slow":
        mastery_delta = 0.03 if time_ratio <= 1.35 else 0.0
        confidence_delta = 0.05
    elif bucket == "wrong":
        mastery_delta = -0.12
        confidence_delta = -0.08
        if time_ratio < 0.65:
            confidence_delta -= 0.03
    else:
        raise ValueError(f"state_analyzer returned invalid bucket: {bucket}")

    updates: Dict[str, Dict[str, float]] = {}
    for kc_id in target_kcs:
        kc = user_state.kcs[kc_id]
        updates[kc_id] = update_kc_with_bkt(kc=kc, correctness=correctness, gamma=gamma)
        updates[kc_id]["heuristic_mastery_delta"] = round(mastery_delta, 4)
        updates[kc_id]["heuristic_confidence_delta"] = round(confidence_delta, 4)

        node_meta = user_state.dag_state.get("nodes", {}).get(kc_id, {})
        node_meta["alpha"] = kc.alpha
        node_meta["beta"] = kc.beta
        node_meta["mastery"] = kc.mastery
        node_meta["confidence"] = kc.confidence
        user_state.dag_state["nodes"][kc_id] = node_meta

    dag_backprop = dag_reverse_propagate(user_state=user_state, source_kc_ids=target_kcs)
    for record in dag_backprop:
        prereq_kc_id = record["to_prereq_kc"]
        prereq = user_state.kcs[prereq_kc_id]
        node_meta = user_state.dag_state.get("nodes", {}).get(prereq_kc_id, {})
        node_meta["alpha"] = prereq.alpha
        node_meta["beta"] = prereq.beta
        node_meta["mastery"] = prereq.mastery
        node_meta["confidence"] = prereq.confidence
        user_state.dag_state["nodes"][prereq_kc_id] = node_meta

    adaptive_tokens = [
        token
        for token in ["把", "被", "了", "过", "虽然", "但是", "其实", "有点", "可以", "应该"]
        if token in user_response_text
    ]
    user_state.vocab_bucket.update(adaptive_tokens)

    user_state.rounds += 1
    user_state.total_actual_time_sec += actual_time_sec
    user_state.total_expected_time_sec += expected_time_sec
    user_state.turn_history.append(
        TurnTrace(
            question=user_state.last_question,
            answer=user_response_text,
            expected_time_sec=expected_time_sec,
            actual_time_sec=actual_time_sec,
            time_ratio=round(time_ratio, 4),
            result_bucket=bucket,
            target_kcs=list(target_kcs),
        )
    )

    return {
        "bucket": bucket,
        "correctness": round(correctness, 4),
        "time_ratio": round(time_ratio, 4),
        "gamma": round(gamma, 4),
        "updates": updates,
        "dag_backprop": dag_backprop,
    }


async def report_agent(user_state: UserState) -> AssessmentReport:
    state_summary = {
        "global_level": user_state.global_level,
        "rounds": user_state.rounds,
        "kcs": {
            kc_id: {
                "alpha": round(kc.alpha, 4),
                "beta": round(kc.beta, 4),
                "mastery": round(kc.mastery, 4),
                "confidence": round(kc.confidence, 4),
            }
            for kc_id, kc in user_state.kcs.items()
        },
        "total_actual_time_sec": round(user_state.total_actual_time_sec, 4),
        "total_expected_time_sec": round(user_state.total_expected_time_sec, 4),
        "turn_history": [item.model_dump() for item in user_state.turn_history[-6:]],
    }
    query = "请严格输出 AssessmentReport JSON，不要附加解释。" f"state_summary: {state_summary}"
    payload = _parse_json_object(await _call_agent("report_agent", query))
    return AssessmentReport.model_validate(payload)


async def agent_f_estimate_difficulty(user_L1: str, kc_id: str) -> float:
    kc = KC_BY_ID.get(kc_id)
    target_kc = kc_id if not kc else f"{kc_id}（{kc.description}）"

    query = AGENT_F_PROMPT.format(user_L1=user_L1, target_kc=target_kc)
    payload = _parse_json_object(await _call_agent("agent_f_feature", query))
    value = payload.get("base_difficulty")
    if not isinstance(value, (int, float)):
        raise ValueError("agent_f_estimate_difficulty: base_difficulty must be numeric")

    return max(0.0, min(3.0, float(value)))
