from __future__ import annotations

from typing import Any, Dict, List, Set

from pydantic import BaseModel, Field


class KCState(BaseModel):
    """单个知识组件状态。"""

    kc_id: str
    alpha: float = Field(gt=0.0)
    beta: float = Field(gt=0.0)
    mastery: float = Field(ge=0.0, le=1.0)
    confidence: float = Field(ge=0.0, le=1.0)


class CognitiveFluency(BaseModel):
    """认知流利度画像。"""

    avg_time_ratio: float = Field(ge=0.0)
    fluency_label: str
    interpretation: str


class DetailedUserProfile(BaseModel):
    """用户详细画像。"""

    radar_chart: Dict[str, float]
    cognitive_fluency: CognitiveFluency
    strengths: List[str]
    weaknesses: List[str]


class AssessmentReport(BaseModel):
    """最终评测报告。"""

    estimated_hsk_level: str
    detailed_user_profile: DetailedUserProfile


class TurnTrace(BaseModel):
    """每轮对话的可解释追踪信息。"""

    question: str
    answer: str
    expected_time_sec: float
    actual_time_sec: float
    time_ratio: float
    result_bucket: str
    target_kcs: List[str]


class UserState(BaseModel):
    """会话级用户状态。

    按提示词要求保留核心字段：
    - session_id
    - kcs
    - vocab_bucket
    - dag_state
    - global_level

    同时补充运行时字段用于编排流程。
    """

    session_id: str
    user_id: str
    kcs: Dict[str, KCState]
    vocab_bucket: Set[str] = Field(default_factory=set)
    dag_state: Dict[str, Any] = Field(default_factory=dict)
    global_level: str

    rounds: int = 0
    max_rounds: int = 6
    total_actual_time_sec: float = 0.0
    total_expected_time_sec: float = 0.0
    last_question: str = ""
    last_expected_time_sec: float = 10.0
    last_target_kcs: List[str] = Field(default_factory=list)
    turn_history: List[TurnTrace] = Field(default_factory=list)
