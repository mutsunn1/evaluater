from typing import Dict, Optional
from pydantic import BaseModel, Field

class KCHLRState(BaseModel):
    kc_id: str
    x_correct: int = 0
    x_wrong: int = 0
    base_difficulty: float = 1.5
    last_attempt_time: Optional[float] = None  # Unix timestamp
    current_half_life: Optional[float] = None  # in days

class UserLearningProfile(BaseModel):
    user_id: str
    user_L1: str = "English"
    hlr_kcs: Dict[str, KCHLRState] = Field(default_factory=dict)
