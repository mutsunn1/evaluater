import json
from typing import Dict, Any
from app.services.kc_catalog import KC_BY_ID

AGENT_F_PROMPT = """
# Role
你是一个资深的语言学教授与记忆认知专家（SLA）。
你需要根据半衰期回归模型（HLR）的理念，评估特定中文知识点对于特定母语者的“初始记忆衰减难度（base_difficulty）”。

# Context
- 目标学习者母语：{user_L1}
- 目标测试知识点 (KC)：{target_kc}

# Task
请进行特征提取（Lexeme Tags），并给出一个初始难度系数 `base_difficulty`。
- `base_difficulty` 必须在 0.0 到 3.0 之间。
- 值越大，表示该知识点越容易遗忘（半衰期越短）。
- 评估标准：
  1. 母语负迁移（如果是英语直译很难对应的中文特有语法，难度极高，> 2.0）
  2. 抽象程度（虚词比实词难记）
  3. 词形相似度（是否容易和其他中文词混淆）

# Output Format (严格输出 JSON)
{
  "kc_id": "{target_kc}",
  "linguistic_features": {
    "pos_tag": "词性",
    "is_language_specific": true,
    "cognitive_load_reason": "简述为什么难/容易记"
  },
  "base_difficulty": 2.5
}
"""

async def agent_f_estimate_difficulty(user_L1: str, kc_id: str) -> float:
    """
    模拟Agent F：调用LLM获取base_difficulty。
    此处为模拟返回逻辑。如果是真实环境，可以将AGENT_F_PROMPT传给LLM进行推理。
    """
    kc = KC_BY_ID.get(kc_id)
    if kc:
        desc = kc.description
        if "了" in desc or "被" in desc or "把" in desc or "补语" in desc:
            return 2.5
        elif kc.tier == 1:
            return 1.2
        elif kc.tier == 2:
            return 1.8
        elif kc.tier >= 3:
            return 2.2
            
    return 1.5
