from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Set, Tuple


@dataclass(frozen=True)
class KCDef:
    kc_id: str
    tier: int
    hsk_band: str
    description: str


KC_DEFS: List[KCDef] = [
    KCDef("G_Adjective_Predicate", 1, "HSK1-2", "形容词谓语句"),
    KCDef("G_WordOrder_TimeLoc", 1, "HSK1-2", "时间/地点状语前置"),
    KCDef("G_Question_VnotV", 1, "HSK1-2", "正反问句"),
    KCDef("V_MeasureWords_Basic", 1, "HSK1-2", "基础量词"),
    KCDef("G_Modal_Can", 1, "HSK1-2", "会/能/可以"),
    KCDef("P_Tone_Sandhi", 1, "HSK1-2", "基础变调"),
    KCDef("G_Particle_Le_Action", 2, "HSK3", "动态助词了"),
    KCDef("G_Particle_Guo", 2, "HSK3", "经验助词过"),
    KCDef("G_Structure_Ba", 2, "HSK3", "把字句"),
    KCDef("G_Complement_Result", 2, "HSK3", "结果补语"),
    KCDef("G_Complement_Direction_Simp", 2, "HSK3", "简单趋向补语"),
    KCDef("G_Comparison_Bi", 2, "HSK3", "比字句"),
    KCDef("G_Duration_Action", 2, "HSK3", "动量/时量表达"),
    KCDef("G_Structure_Bei", 3, "HSK4", "被字句"),
    KCDef("G_Complement_Potential", 3, "HSK4", "可能补语"),
    KCDef("G_Complement_Direction_Comp", 3, "HSK4", "复合趋向补语"),
    KCDef("G_Structure_ShiDe", 3, "HSK4", "是...的强调句"),
    KCDef("G_Conjunction_Paired", 3, "HSK4", "成对关联词"),
    KCDef("PR_Softener_Youdian", 3, "HSK4", "有点儿委婉语"),
    KCDef("G_Topic_Comment", 4, "HSK5-6", "话题说明结构"),
    KCDef("G_Rhetorical_Question", 4, "HSK5-6", "反问句式"),
    KCDef("V_Formal_Written", 4, "HSK5-6", "语体切换"),
    KCDef("V_Idiom_Contextual", 4, "HSK5-6", "语境成语"),
    KCDef("G_Adverb_Tone", 4, "HSK5-6", "语气副词"),
    KCDef("PR_Discourse_Fillers", 4, "HSK5-6", "话语标记"),
]

KC_BY_ID: Dict[str, KCDef] = {item.kc_id: item for item in KC_DEFS}

LEVEL_TO_TIER = {
    "BEGINNER": 1,
    "INTERMEDIATE": 2,
    "ADVANCED": 4,
}


LEVEL_VOCAB_BUCKET: Dict[str, Set[str]] = {
    "BEGINNER": {"今天", "昨天", "可以", "喜欢", "觉得", "因为", "所以"},
    "INTERMEDIATE": {
        "把",
        "被",
        "已经",
        "刚刚",
        "虽然",
        "但是",
        "应该",
        "比较",
        "结果",
    },
    "ADVANCED": {
        "尽管",
        "然而",
        "未必",
        "不见得",
        "换句话说",
        "从而",
        "以至于",
        "有点儿",
        "其实",
    },
}


KC_KEYWORD_RULES: Dict[str, List[str]] = {
    "G_Structure_Ba": ["把"],
    "G_Structure_Bei": ["被"],
    "G_Particle_Le_Action": ["了"],
    "G_Particle_Guo": ["过"],
    "G_Comparison_Bi": ["比"],
    "G_Modal_Can": ["会", "能", "可以"],
    "G_Question_VnotV": ["不", "吗"],
    "G_Conjunction_Paired": ["虽然", "但是", "不但", "而且"],
    "PR_Softener_Youdian": ["有点", "有一点"],
    "PR_Discourse_Fillers": ["其实", "就是", "怎么说呢"],
}


def build_initial_dag_state() -> Dict[str, object]:
    """构建简化的知识图谱状态。

    节点表示知识组件，边表示先修关系。
    """
    edges = [
        ("G_Adjective_Predicate", "G_Comparison_Bi"),
        ("G_Modal_Can", "G_Complement_Potential"),
        ("G_Particle_Le_Action", "G_Particle_Guo"),
        ("G_Structure_Ba", "G_Structure_Bei"),
        ("G_Complement_Result", "G_Complement_Potential"),
        ("G_Conjunction_Paired", "G_Rhetorical_Question"),
    ]

    default_weight = 0.35
    return {
        "nodes": {kc.kc_id: {"tier": kc.tier, "description": kc.description} for kc in KC_DEFS},
        "edges": [{"from": src, "to": dst, "weight": default_weight} for src, dst in edges],
    }


def build_level_seed(self_assessed_level: str) -> Tuple[float, float, Set[str], int]:
    """根据用户自评等级返回初始 mastery/confidence/词汇桶/目标层级。"""
    if self_assessed_level == "BEGINNER":
        return 0.22, 0.35, set(LEVEL_VOCAB_BUCKET["BEGINNER"]), 1
    if self_assessed_level == "INTERMEDIATE":
        vocab = set(LEVEL_VOCAB_BUCKET["BEGINNER"]) | set(LEVEL_VOCAB_BUCKET["INTERMEDIATE"])
        return 0.50, 0.45, vocab, 2

    vocab = set().union(*LEVEL_VOCAB_BUCKET.values())
    return 0.75, 0.55, vocab, 4


def build_question_bank() -> Dict[str, List[str]]:
    """按KC提供开放式对话题模板。"""
    return {
        "G_Structure_Ba": [
            "你准备搬家，怎么把你的衣服和书整理进箱子？",
            "如果房间很乱，你会先把什么收起来？为什么？",
        ],
        "G_Structure_Bei": [
            "你最近有没有被什么事情打乱计划？具体说说。",
            "讲一次你被别人误会的经历，你是怎么处理的？",
        ],
        "G_Particle_Le_Action": [
            "你今天已经做了哪些事？请按顺序说一下。",
            "昨天晚上你回家以后做了什么？",
        ],
        "G_Comparison_Bi": [
            "你觉得线上学习和线下学习比起来，哪个更适合你？",
            "在你看来，早起和熬夜哪一个对效率影响更大？",
        ],
    }
