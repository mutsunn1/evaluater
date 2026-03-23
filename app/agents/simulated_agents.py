from __future__ import annotations

import math
from typing import Dict, List, Tuple

from app.models.domain import AssessmentReport, CognitiveFluency, DetailedUserProfile, UserState
from app.services.kc_catalog import KC_BY_ID, LEVEL_TO_TIER


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


def _avg_confidence(user_state: UserState) -> float:
    if not user_state.kcs:
        return 0.0
    return sum(kc.confidence for kc in user_state.kcs.values()) / len(user_state.kcs)


async def agent_c_strategy(user_state: UserState) -> Dict[str, object]:
    target_tier = LEVEL_TO_TIER.get(user_state.global_level, 2)
    candidate_ids = [
        kc_id
        for kc_id in user_state.kcs
        if KC_BY_ID.get(kc_id) and KC_BY_ID[kc_id].tier <= target_tier + 1
    ]
    if not candidate_ids:
        candidate_ids = list(user_state.kcs.keys())

    ranked = sorted(candidate_ids, key=lambda x: user_state.kcs[x].confidence)
    target_kcs = ranked[:2]

    scene_bits = [KC_BY_ID[kc].description for kc in target_kcs if kc in KC_BY_ID]
    scene_guideline = "请在生活化场景中引导用户自然使用：" + "、".join(scene_bits or ["目标语法点"])

    global_conf = _avg_confidence(user_state)
    should_stop = global_conf > 0.85 or user_state.rounds > 5
    reason = f"global_confidence={global_conf:.3f}, rounds={user_state.rounds}"

    return {
        "target_kcs": target_kcs,
        "scene_guideline": scene_guideline,
        "should_stop": should_stop,
        "reason": reason,
    }


async def agent_a_roleplay(scene_guideline: str, target_kcs: List[str]) -> str:
    lead_kc = target_kcs[0] if target_kcs else "G_Adjective_Predicate"

    templates = {
        "G_Structure_Ba": "你的桌子很乱，你会怎么整理这些书和笔？",
        "G_Structure_Bei": "你最近有没有遇到什么倒霉事？可以具体说说吗？",
        "G_Particle_Le_Action": "你昨天晚上做了什么？请用完整句子回答。",
        "G_Comparison_Bi": "你觉得线上学习和线下学习，哪一个更适合你？为什么？",
    }
    return templates.get(lead_kc, f"{scene_guideline}。请你用一句自然的中文完整回答。")


async def agent_e_time_estimator(question: str, user_state: UserState, target_kcs: List[str]) -> Dict[str, float]:
    t_perception = max(4.0, len(question) * 0.18)

    if target_kcs:
        mastery_values = [user_state.kcs[k].mastery for k in target_kcs if k in user_state.kcs]
    else:
        mastery_values = [kc.mastery for kc in user_state.kcs.values()]
    mastery_avg = sum(mastery_values) / max(1, len(mastery_values))

    t_retrieval = 8.0 * (1.05 - mastery_avg)
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


def _content_correctness(user_text: str, target_kcs: List[str]) -> float:
    text = user_text.strip()
    if not text:
        return 0.0

    pattern_score = 0.0
    for kc in target_kcs:
        if kc == "G_Structure_Ba" and "把" in text:
            pattern_score += 1.0
        elif kc == "G_Structure_Bei" and "被" in text:
            pattern_score += 1.0
        elif kc == "G_Particle_Le_Action" and "了" in text:
            pattern_score += 1.0
        elif kc == "G_Particle_Guo" and "过" in text:
            pattern_score += 1.0
        elif kc == "G_Comparison_Bi" and "比" in text:
            pattern_score += 1.0
        elif kc == "G_Question_VnotV" and "不" in text:
            pattern_score += 0.8
        elif kc == "G_Modal_Can" and any(x in text for x in ["会", "能", "可以"]):
            pattern_score += 0.8
        elif kc.startswith("PR_") and any(x in text for x in ["有点", "其实", "就是", "怎么说呢"]):
            pattern_score += 0.8

    length_bonus = 0.2 if len(text) >= 8 else 0.0
    raw = pattern_score / max(1, len(target_kcs)) + length_bonus
    return max(0.0, min(1.0, raw))


async def agent_b_time_penalized_evaluator(
    user_state: UserState,
    user_response_text: str,
    actual_time_sec: float,
    expected_time_sec: float,
    target_kcs: List[str],
) -> Dict[str, object]:
    if not target_kcs:
        target_kcs = sorted(user_state.kcs.keys(), key=lambda k: user_state.kcs[k].confidence)[:1]

    correctness = _content_correctness(user_response_text, target_kcs)
    time_ratio = actual_time_sec / max(0.1, expected_time_sec)

    # 下面是时间惩罚核心逻辑：
    # 1) 先判断回答是否“足够正确”，用 correctness >= 0.6 作为阈值。
    # 2) 若正确，再根据 actual/expected 的比值判断是“自动化流畅输出”还是“慢速检索输出”。
    # 3) 若错误，不管快慢，均执行较大幅度扣分，避免“快但错”被误判为高能力。
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

    user_state.rounds += 1
    user_state.total_actual_time_sec += actual_time_sec
    user_state.total_expected_time_sec += expected_time_sec
    user_state.conversation_history.append(
        {
            "question": user_state.last_question,
            "answer": user_response_text,
            "result_bucket": bucket,
            "time_ratio": f"{time_ratio:.3f}",
        }
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
