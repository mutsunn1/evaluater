import time
from typing import Dict
from app.models.hlr_domain import KCHLRState, UserLearningProfile
from app.services.hlr_engine import HLREngine
from app.agents.agent_f_feature import agent_f_estimate_difficulty

# 模拟辅助模块数据库
LEARNING_PROFILES: Dict[str, UserLearningProfile] = {}
hlr_engine = HLREngine()

async def get_or_create_profile(user_id: str, user_L1: str = "English") -> UserLearningProfile:
    if user_id not in LEARNING_PROFILES:
        LEARNING_PROFILES[user_id] = UserLearningProfile(user_id=user_id, user_L1=user_L1)
    return LEARNING_PROFILES[user_id]

async def record_learning_event(user_id: str, kc_id: str, is_correct: bool, current_time: float = None):
    profile = await get_or_create_profile(user_id)
    if current_time is None:
        current_time = time.time()
        
    if kc_id not in profile.hlr_kcs:
        base_diff = await agent_f_estimate_difficulty(profile.user_L1, kc_id)
        kc_state = KCHLRState(kc_id=kc_id, base_difficulty=base_diff)
        profile.hlr_kcs[kc_id] = kc_state
    else:
        kc_state = profile.hlr_kcs[kc_id]
        
    if is_correct:
        kc_state.x_correct += 1
    else:
        kc_state.x_wrong += 1
        
    kc_state.last_attempt_time = current_time
    kc_state.current_half_life = hlr_engine.calculate_half_life(
        kc_state.x_correct,
        kc_state.x_wrong,
        kc_state.base_difficulty
    )
    return kc_state

def query_kc_retention(user_id: str, kc_id: str, query_time: float = None) -> float:
    if user_id not in LEARNING_PROFILES:
        return 0.0
    profile = LEARNING_PROFILES[user_id]
    if kc_id not in profile.hlr_kcs:
        return 0.0
        
    kc_state = profile.hlr_kcs[kc_id]
    if kc_state.current_half_life is None or kc_state.last_attempt_time is None:
        return 0.0
        
    if query_time is None:
        query_time = time.time()
        
    delta_days = (query_time - kc_state.last_attempt_time) / (3600.0 * 24.0)
    p = hlr_engine.predict_recall_probability(kc_state.current_half_life, delta_days)
    return p
