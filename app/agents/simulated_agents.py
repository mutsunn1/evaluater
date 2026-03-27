from __future__ import annotations

from random import choice
from typing import Dict, List, Set

from app.models.domain import AssessmentReport, CognitiveFluency, DetailedUserProfile, TurnTrace, UserState
from app.services.kc_catalog import KC_BY_ID, KC_KEYWORD_RULES, build_question_bank


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


def _avg_confidence(user_state: UserState) -> float:
    if not user_state.kcs:
        return 0.0
    return sum(kc.confidence for kc in user_state.kcs.values()) / len(user_state.kcs)


async def kc_planner_agent(user_state: UserState) -> Dict[str, object]:
    """KC 规划者：基于当前状态选择下一轮目标 KC。"""
    target_tier = user_state.dag_state.get("target_tier", 2)
    candidate_ids = [
        kc_id
        for kc_id in user_state.kcs
        if KC_BY_ID.get(kc_id) and KC_BY_ID[kc_id].tier <= target_tier + 1
    ]
    if not candidate_ids:
        candidate_ids = list(user_state.kcs.keys())

    # 先找置信度最低的点，再按掌握度排序，优先追踪“低置信+低掌握”的薄弱点。
    ranked = sorted(candidate_ids, key=lambda x: (user_state.kcs[x].confidence, user_state.kcs[x].mastery))
    target_kcs = ranked[:2] if len(ranked) >= 2 else ranked[:1]

    scene_bits = [KC_BY_ID[kc].description for kc in target_kcs if kc in KC_BY_ID]
    scene_guideline = "请在生活化场景中引导用户自然使用：" + "、".join(scene_bits or ["目标语法点"])

    global_conf = _avg_confidence(user_state)
    mastery_avg = sum(k.mastery for k in user_state.kcs.values()) / max(1, len(user_state.kcs))
    should_stop = global_conf > 0.86 or user_state.rounds >= user_state.max_rounds or mastery_avg > 0.82
    reason = f"global_confidence={global_conf:.3f}, rounds={user_state.rounds}"

    return {
        "target_kcs": target_kcs,
        "scene_guideline": scene_guideline,
        "should_stop": should_stop,
        "reason": reason,
    }


async def question_selector_agent(scene_guideline: str, target_kcs: List[str]) -> str:
    """题目挑选者：按目标 KC 生成或挑选开放式题目。"""
    bank = build_question_bank()
    lead_kc = target_kcs[0] if target_kcs else "G_Adjective_Predicate"
    if lead_kc in bank:
        return choice(bank[lead_kc])

    return f"{scene_guideline}。请用2到3句自然中文回答。"


async def time_analyzer_agent(question: str, user_state: UserState, target_kcs: List[str]) -> Dict[str, float]:
    """耗时分析器：估计当前题目的预期答题时间。"""
    t_perception = max(4.0, len(question) * 0.18)

    if target_kcs:
        mastery_values = [user_state.kcs[k].mastery for k in target_kcs if k in user_state.kcs]
    else:
        mastery_values = [kc.mastery for kc in user_state.kcs.values()]
    mastery_avg = sum(mastery_values) / max(1, len(mastery_values))

    # mastery 越低，检索越慢；给一个下限避免极端值导致估计异常。
    t_retrieval = max(1.8, 8.0 * (1.05 - mastery_avg))
    punctuation_penalty = question.count("，") * 0.3 + question.count("？") * 0.4
    structure_bonus = 1.2 if any(kc.startswith("G_Complement") for kc in target_kcs) else 0.6
    complexity_bonus = max(0.4, punctuation_penalty + structure_bonus)

    expected = round(max(5.0, t_perception + t_retrieval + complexity_bonus), 2)
    return {
        "expected_time_sec": expected,
        "t_perception": round(t_perception, 2),
        "t_retrieval": round(t_retrieval, 2),
        "complexity_bonus": round(complexity_bonus, 2),
    }


def _keyword_hit_count(text: str, keywords: List[str]) -> int:
    """统计关键词命中次数。

    这里使用简单字串匹配，不做分词，以满足提示词中“词汇与前后缀可直接字串识别”的要求。
    """
    return sum(1 for kw in keywords if kw and kw in text)


def _content_correctness(user_text: str, target_kcs: List[str], vocab_bucket: Set[str]) -> float:
    text = user_text.strip()
    if not text:
        return 0.0

    pattern_score = 0.0
    for kc in target_kcs:
        keys = KC_KEYWORD_RULES.get(kc, [])
        hit = _keyword_hit_count(text, keys)
        if hit > 0:
            pattern_score += min(1.0, 0.5 + 0.25 * hit)

    # 与词汇桶重合越高，说明输出词汇与当前可用词汇系统越一致。
    bucket_hits = sum(1 for token in vocab_bucket if token in text)
    bucket_bonus = min(0.25, 0.03 * bucket_hits)
    length_bonus = 0.15 if len(text) >= 8 else 0.0
    raw = pattern_score / max(1, len(target_kcs)) + length_bonus + bucket_bonus
    return max(0.0, min(1.0, raw))


async def state_analyzer_agent(
    user_state: UserState,
    user_response_text: str,
    actual_time_sec: float,
    expected_time_sec: float,
    target_kcs: List[str],
) -> Dict[str, object]:
    """状态分析者：执行时间惩罚与状态迁移。

    包含三部分核心动作：
    1) 计算内容正确性与时间比。
    2) 应用时间惩罚矩阵更新 mastery/confidence。
    3) 按回答中的字串命中更新词汇桶与 DAG 节点状态。
    """
    if not target_kcs:
        target_kcs = sorted(user_state.kcs.keys(), key=lambda k: user_state.kcs[k].confidence)[:1]

    correctness = _content_correctness(user_response_text, target_kcs, user_state.vocab_bucket)
    time_ratio = actual_time_sec / max(0.1, expected_time_sec)

    # 时间惩罚核心矩阵（与提示词保持一致）：
    # - 正确且快：mastery 大幅增加
    # - 正确但慢：mastery 小幅增加或不变
    # - 错误：mastery 大幅下降
    if correctness >= 0.6 and actual_time_sec < expected_time_sec:
        mastery_delta = 0.12
        confidence_delta = 0.10
        bucket = "correct_fast"
    elif correctness >= 0.6 and actual_time_sec >= expected_time_sec:
        # 正确但慢：说明可能是“陈述性知识”阶段，规则上只给小幅增益。
        if time_ratio <= 1.35:
            mastery_delta = 0.03
        else:
            mastery_delta = 0.0
        confidence_delta = 0.05
        bucket = "correct_slow"
    else:
        # 错误：大幅扣分。
        mastery_delta = -0.12
        confidence_delta = -0.08
        # 额外惩罚：如果明显超快但错误，通常是猜测或模板化乱答，再扣一点 confidence。
        if time_ratio < 0.65:
            confidence_delta -= 0.03
        bucket = "wrong"

    updates: Dict[str, Dict[str, float]] = {}
    for kc_id in target_kcs:
        kc = user_state.kcs[kc_id]
        before_mastery = kc.mastery
        before_conf = kc.confidence
        kc.mastery = _clamp01(kc.mastery + mastery_delta)
        kc.confidence = _clamp01(kc.confidence + confidence_delta)
        updates[kc_id] = {
            "mastery_before": round(before_mastery, 4),
            "mastery_after": round(kc.mastery, 4),
            "confidence_before": round(before_conf, 4),
            "confidence_after": round(kc.confidence, 4),
        }

        # DAG 节点状态同步更新，便于后续图谱可视化或调度策略解释。
        node_meta = user_state.dag_state.get("nodes", {}).get(kc_id, {})
        node_meta["mastery"] = kc.mastery
        node_meta["confidence"] = kc.confidence
        user_state.dag_state["nodes"][kc_id] = node_meta

    # 词汇桶增量更新：把用户回答中命中的高频词加入桶，形成动态词汇画像。
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
        "updates": updates,
    }


async def report_agent(user_state: UserState) -> AssessmentReport:
    mastery_avg = sum(kc.mastery for kc in user_state.kcs.values()) / max(1, len(user_state.kcs))
    if mastery_avg < 0.35:
        estimated_hsk = "HSK 1-2"
    elif mastery_avg < 0.58:
        estimated_hsk = "HSK 3"
    elif mastery_avg < 0.75:
        estimated_hsk = "HSK 4"
    else:
        estimated_hsk = "HSK 5-6"

    grammar_kcs = [kc for kc_id, kc in user_state.kcs.items() if kc_id.startswith("G_")]
    vocab_kcs = [kc for kc_id, kc in user_state.kcs.items() if kc_id.startswith("V_")]
    pragmatics_kcs = [kc for kc_id, kc in user_state.kcs.items() if kc_id.startswith("PR_")]
    phonetics_kcs = [kc for kc_id, kc in user_state.kcs.items() if kc_id.startswith("P_")]

    def avg(items: List[object]) -> float:
        if not items:
            return 0.0
        return sum(x.mastery for x in items) / len(items)

    radar = {
        "grammar": round(avg(grammar_kcs), 3),
        "vocabulary": round(avg(vocab_kcs), 3),
        "pragmatics": round(avg(pragmatics_kcs), 3),
        "phonetics": round(avg(phonetics_kcs), 3),
        "overall": round(mastery_avg, 3),
    }

    avg_time_ratio = user_state.total_actual_time_sec / max(1.0, user_state.total_expected_time_sec)
    if avg_time_ratio < 0.9:
        fluency_label = "自动化输出"
        interpretation = "你的响应速度普遍快于系统预期，检索负荷较低。"
    elif avg_time_ratio <= 1.15:
        fluency_label = "稳定输出"
        interpretation = "你的耗时与预期基本一致，认知负荷可控。"
    else:
        fluency_label = "慢速检索"
        interpretation = "你的回答内容可能正确，但检索速度偏慢，建议加强高频句式自动化。"

    sorted_kcs = sorted(user_state.kcs.values(), key=lambda k: k.mastery, reverse=True)
    strengths = [f"{kc.kc_id} ({kc.mastery:.2f})" for kc in sorted_kcs[:5]]
    weaknesses = [f"{kc.kc_id} ({kc.mastery:.2f})" for kc in sorted_kcs[-5:]]

    profile = DetailedUserProfile(
        radar_chart=radar,
        cognitive_fluency=CognitiveFluency(
            avg_time_ratio=round(avg_time_ratio, 3),
            fluency_label=fluency_label,
            interpretation=interpretation,
        ),
        strengths=strengths,
        weaknesses=weaknesses,
    )
    return AssessmentReport(estimated_hsk_level=estimated_hsk, detailed_user_profile=profile)
