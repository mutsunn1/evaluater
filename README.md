# Time-Penalized GENCAT 中文水平评测后端

## 目录结构

```text
.
├── app
│   ├── api
│   │   └── assessment.py
│   ├── agents
│   │   ├── prompts.py
│   │   ├── simulated_agents.py
│   │   └── oxygent_workflows.py
│   ├── models
│   │   ├── domain.py
│   │   └── schemas.py
│   ├── services
│   │   ├── assessment_service.py
│   │   └── kc_catalog.py
│   ├── store
│   │   └── memory_db.py
│   └── main.py
├── main.py
├── kcs_template.md
├── prompt.md
└── requirements.txt
```

## 快速启动

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload
```

## REST API

1. `POST /api/assessment/start`
2. `POST /api/assessment/chat`
3. `GET /api/assessment/report/{session_id}`

## OxyGent Pipeline 说明

- 启动阶段：`Agent C -> Agent A -> Agent E`
- 聊天阶段：`Agent B -> Agent C -> (未结束时) Agent A -> Agent E`

可参考 `app/agents/oxygent_workflows.py` 中的 `assessment_start_workflow` 与 `assessment_chat_workflow`。
