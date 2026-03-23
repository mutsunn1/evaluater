from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List


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
    "ADVANCED": 3,
}
