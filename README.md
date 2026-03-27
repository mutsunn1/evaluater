# Time-Penalized GENCAT 中文水平评测后端

本项目实现了一个基于开放式对话与时间惩罚机制的中文水平自适应评测后端。

## 核心能力

- FastAPI RESTful 三接口：start / chat / report
- Pydantic 强类型数据校验
- 基于内存 Dict 的会话状态管理（session_id -> UserState）
- 多智能体协作流程：KC Planner、Question Selector、Time Analyzer、State Analyzer
- 词汇桶 + DAG 状态协同更新

## 目录结构

```text
.
├── app
│   ├── agents
│   │   ├── prompts.py
│   │   ├── simulated_agents.py
│   │   └── oxygent_workflows.py
│   ├── api
│   │   └── assessment.py
│   ├── models
│   │   ├── domain.py
│   │   └── schemas.py
│   ├── services
│   │   ├── assessment_service.py
│   │   ├── kc_catalog.py
│   │   └── pipeline.py
│   ├── store
│   │   └── memory_db.py
│   └── main.py
├── main.py
├── requirements.txt
└── test_endpoints.py
```

## 快速启动

```bash
pip install -r requirements.txt
uvicorn app.main:app --host 127.0.0.1 --port 18000 --reload
```

## REST API

### 1) POST /api/assessment/start

请求：

```json
{
  "user_id": "u001",
  "self_assessed_level": "BEGINNER"
}
```

响应：

```json
{
  "session_id": "...",
  "first_question": "...",
  "expected_time_sec": 12.0
}
```

### 2) POST /api/assessment/chat

请求：

```json
{
  "session_id": "...",
  "user_response_text": "我把书放在桌子上了。",
  "actual_time_sec": 8.5
}
```

完成时响应：

```json
{
  "status": "completed",
  "redirect_url": "/api/assessment/report/{session_id}"
}
```

未完成时响应：

```json
{
  "status": "in_progress",
  "next_question": "...",
  "expected_time_sec": 11.2
}
```

### 3) GET /api/assessment/report/{session_id}

返回结构化报告：

- estimated_hsk_level
- detailed_user_profile.radar_chart
- detailed_user_profile.cognitive_fluency
- detailed_user_profile.strengths
- detailed_user_profile.weaknesses

## OxyGent 编排说明

- 业务运行默认采用本地 async 模拟 Agent（便于离线快速验证）。
- 同时提供 OxyGent 标准组装代码，见 app/agents/oxygent_workflows.py。
- 默认开启 STRICT_SPEC_MODE=1，会对主流程输出进行规范序列校验。
