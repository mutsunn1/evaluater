from __future__ import annotations

from typing import Dict

from app.models.domain import UserState

# 用 Python 字典模拟数据库，按 session_id 持久化一次评测会话。
SESSIONS: Dict[str, UserState] = {}
