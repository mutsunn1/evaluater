# Role: 高级 AI 后端工程师 & 教育测量学专家

## 1. 项目概述
你需要使用 Python 开发一个基于“带时间惩罚的生成式自适应测试（Time-Penalized GENCAT）”的中文语言水平（SLA）评测后端系统。
该系统摒弃传统的选择题，通过多轮开放式对话（Roleplay）以及回答的绝对耗时，动态评估用户的中文水平。

## 2. 技术栈约束
- **Web 框架**: FastAPI (要求完全遵循 RESTful API 设计规范)。
- **Agent 框架**: `oxygent` (京东开源的多智能体协作框架。请利用其 Agent、LLM、Pipeline/Workflow 等核心组件机制进行编排)。文档参考: `https://github.com/jd-opensource/OxyGent/blob/main/docs/docs_zh/readme.md`
- **数据校验**: Pydantic。
- **存储**: 使用 Python 内存 `Dict` 模拟 DB 存储不同用户的 `session_id` 和状态。

## 3. 核心数据模型 (Pydantic Models)
请严格定义以下模型：
1. `KCState`: 包含 `kc_id` (str), `mastery` (float, 0-1), `confidence` (float, 0-1).
2. `UserState`: 包含 `session_id`, `kcs` (Dict[str, KCState]), `global_level` (str).
3. `AssessmentReport`: 最终的 JSON 报告模型，必须包含字段：
   - `estimated_hsk_level`: 评测出的 HSK 等级 (如 "HSK 3").
   - `detailed_user_profile`: 详细画像对象，包含 `radar_chart` (各语法维度得分), `cognitive_fluency` (认知流利度分析，基于时间惩罚计算得出), `strengths` (优势), `weaknesses` (待强化项).

## 4. RESTful API 接口定义
请使用 FastAPI 实现以下 3 个核心接口：

### 接口 1: `POST /api/assessment/start`
- **请求体**: `{"user_id": "str", "self_assessed_level": "BEGINNER | INTERMEDIATE | ADVANCED"}`
- **业务逻辑**:
  1. 生成唯一的 `session_id`。
  2. 根据 `self_assessed_level` 初始化用户的 $\theta$ (mastery) 和 confidence。
     - BEGINNER: mastery=0.2, confidence=0.4
     - INTERMEDIATE: mastery=0.5, confidence=0.4
     - ADVANCED: mastery=0.8, confidence=0.4
  3. 调度 OxyGent Pipeline (Agent C -> Agent A -> Agent E)。
- **返回值**: `{"session_id": "...", "first_question": "...", "expected_time_sec": 12.0}`

### 接口 2: `POST /api/assessment/chat`
- **请求体**: `{"session_id": "str", "user_response_text": "str", "actual_time_sec": float}`
- **业务逻辑**:
  1. 调用 Agent B，传入用户的回答、`actual_time_sec` 和上一轮生成的 `expected_time_sec`。Agent B 结合时间差(Δt)更新 `UserState`。
  2. 调用 Agent C 检查是否满足终止条件 (全局 confidence > 0.85 或轮数 > 5)。
     - 如果满足，返回 `{"status": "completed", "redirect_url": "/api/assessment/report/{session_id}"}`
     - 如果不满足，调用 Agent A 生成下一题，并调用 Agent E 算出这道题的 `expected_time_sec`。
- **返回值**: 包含状态、下一题文本和预期时间。

### 接口 3: `GET /api/assessment/report/{session_id}`
- **业务逻辑**: 提取最终的 `UserState`，调用一个 Report Agent 将原始向量转化为结构化的 `AssessmentReport` 模型。
- **返回值**: 格式化的 JSON 报告 (与 `AssessmentReport` 模型一致)。

## 5. OxyGent 多智能体定义 (业务核心)
请使用 `oxygent` 框架定义以下 4 个 Agent，并配置明确的 Prompt：

- **Agent C (Strategy Agent / 路由者)**: 读取当前 `UserState`，找出 confidence 最低且符合当前预估水平的知识组件 (KC)，输出 `target_kcs` 和下一轮对话场景指引。
- **Agent A (Roleplay Agent / 提问者)**: 接收场景指引，生成一句自然的中文对话引导语，诱导用户使用目标 KC（如生成需要用“把”字句回答的情境）。
- **Agent E (Cognitive Load Estimator / 认知时间估算器)**: 采用混合算法。阅读题目计算 $T_{感知}$，结合用户的 $\theta$ 向量计算 $T_{检索}$。并使用轻量级 LLM 调用评估这道题的造句复杂度。最终输出绝对客观的 `expected_time_sec`。
- **Agent B (Time-Penalized Evaluator / 时序惩罚评估官)**: 这是核心。接收用户的真实回答文本和时间差。Prompt 必须体现评估矩阵：
  - 正确且快 (实际耗时 < 预期耗时)：自动化输出，mastery 大幅增加。
  - 正确但慢 (实际耗时 > 预期耗时)：陈述性知识，mastery 微增或不变。
  - 错误：大幅扣分。

## 6. 开发要求
1. 请提供完整的目录结构 (如 `main.py`, `models/`, `agents/`, `api/`)。
2. 给出符合 OxyGent 写法的 Pipeline 组装代码。
3. 请使用 Python 3.10+ 的原生协程 `async/await`，确保高并发下的 Web 性能。
4. 在核心代码（特别是 Agent B 的时间惩罚逻辑处）添加详细的中文注释。