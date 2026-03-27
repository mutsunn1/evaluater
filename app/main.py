from __future__ import annotations

import sys
from pathlib import Path

from fastapi import FastAPI

# 兼容直接执行 app/main.py：将项目根目录加入模块搜索路径。
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

try:
    # 作为包运行（例如 uvicorn app.main:app）
    from app.api.assessment import router as assessment_router
except ModuleNotFoundError:
    # 作为脚本直跑（例如 python app/main.py）
    from api.assessment import router as assessment_router

app = FastAPI(
    title="Time-Penalized GENCAT SLA Assessment API",
    version="1.0.0",
    description="基于多轮开放式对话与时间惩罚的中文水平自适应评测后端",
)

app.include_router(assessment_router)


@app.get("/healthz")
async def healthz() -> dict:
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)
