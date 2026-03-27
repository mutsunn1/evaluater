# Role: 高级 AI 后端工程师 & 教育测量学专家

## 1. 项目概述
你需要使用 Python 开发一个基于“带时间惩罚的生成式自适应测试（Time-Penalized GENCAT）”的中文语言水平（SLA）评测后端系统。
该系统摒弃传统的选择题，通过多轮开放式对话（Roleplay）以及回答的绝对耗时，动态评估用户的中文水平。

### 1.1 项目结构优缺点分析
- **优点**：类 GENCAT 结构使用了严格的知识组件（KC）、词汇桶和知识图谱来限制模型输出，相较其他的简单结构提高了评测的可解释性和准确度。
- **缺点**：复杂的结构（多智能体协同、各种组件的交互）使得评测流程会较为缓慢，在实际应用中需要优化用户体验（例如采用异步流式响应、占位提示等）。

## 2. 技术栈约束
- **Web 框架**: FastAPI (要求完全遵循 RESTful API 设计规范)。
- **Agent 框架**: oxygent (京东开源的多智能体协作框架。请利用其 Agent、LLM、Pipeline/Workflow 等核心组件机制进行编排)。文档参考: https://github.com/jd-opensource/OxyGent/blob/main/docs/docs_zh/readme.md
- **数据校验**: Pydantic。
- **存储**: 使用 Python 内存 Dict 模拟 DB 存储不同用户的 session_id 和状态。

## 3. 核心机制设计

### 3.1 词汇桶与知识图谱的构建
- **核心逻辑**：针对直接给出的完整词汇和前后缀可直接做简单的字串识别。
- **初始化**：初始状态由用户手动选择设定，并基于此构建基础的词汇桶和对应的知识图谱节点。

### 3.2 核心数据模型 (Pydantic Models)
请严格定义以下模型：
1. KCState: 包含 kc_id (str), mastery (float, 0-1), confidence (float, 0-1).
2. UserState: 包含 session_id, kcs (Dict[str, KCState]), ocab_bucket (List[str]或Set), dag_state (Dict), global_level (str).
3. AssessmentReport: 最终的 JSON 报告模型，必须包含字段：
   - stimated_hsk_level: 评测出的 HSK 等级 (如 "HSK 3").
   - detailed_user_profile: 详细画像对象，包含 adar_chart (各语法维度得分), cognitive_fluency (认知流利度分析，基于时间惩罚计算得出), strengths (优势), weaknesses (待强化项).

## 4. OxyGent 多智能体定义与评测流程 (业务核心)
整个评测流程由一个**主 Agent (Main Agent)** 控制流转，包含以下核心组件/子 Agent 角色：

- **KC 规划者 (KC Planner)**: 基于此前判断的用户状态（使用词汇桶和知识图谱，初始状态由用户选择），生成下一步需要考察的 KC（如：“把”字句）。
- **题目挑选者 (Question Selector)**: 接收 KC 规划者的要求，生成对应题目或从题库中挑选题目。
- **耗时分析器 (Time Analyzer)**: 根据题目文本和此前判断的用户水平来判断用户在这道题上可能耗费的预期时间。
- **状态分析者 (State Analyzer)**: 根据所有信息（包含用户的回答、实际耗时、题目预期耗时等）来进行状态迁移。如果在后续流程发现此时间与实际时间耗时发生偏移，即可较大幅度地更新图谱(DAG)、词汇桶乃至全局信息。评估矩阵要求体现：
  - 正确且快 (实际耗时 < 预期耗时)：自动化输出，mastery 大幅增加。
  - 正确但慢 (实际耗时 > 预期耗时)：陈述性知识，mastery 微增或不变。
  - 错误：大幅扣分。

## 5. RESTful API 接口定义
请使用 FastAPI 实现以下 3 个核心接口，体现上述流程：

### 接口 1: POST /api/assessment/start
- **请求体**: {"user_id": "str", "self_assessed_level": "BEGINNER | INTERMEDIATE | ADVANCED"}
- **业务逻辑**:
  1. 生成唯一的 session_id。
  2. 根据 self_assessed_level 初始化用户的状态、词汇桶及知识图谱。
  3. 主 Agent 调度: KC 规划者 -> 题目挑选者 -> 耗时分析器。
- **返回值**: {"session_id": "...", "first_question": "...", "expected_time_sec": 12.0}

### 接口 2: POST /api/assessment/chat
- **请求体**: {"session_id": "str", "user_response_text": "str", "actual_time_sec": float}
- **业务逻辑**:
  1. 调用 **状态分析者** 进行时序惩罚计算与状态迁移 (更新 DAG 与词汇桶)。
  2. 检查是否满足终止条件。
     - 如果满足，返回 {"status": "completed", "redirect_url": "/api/assessment/report/{session_id}"}
     - 如果不满足，主 Agent 继续调度: KC 规划者 -> 题目挑选者 -> 耗时分析器。
- **返回值**: 包含状态、下一题文本和预期时间。

### 接口 3: GET /api/assessment/report/{session_id}
- **业务逻辑**: 提取最终的 UserState，转化为结构化的 AssessmentReport 模型。
- **返回值**: 格式化的 JSON 报告。

## 6. 开发要求
1. 请提供完整的目录结构 (如 main.py, models/, gents/, pi/)。
2. 给出符合 OxyGent 写法的 Pipeline 组装代码（体现主 Agent 控制与各个组件/Agent的配合）。
3. 请使用 Python 3.10+ 的原生协程 sync/await，确保高并发下的 Web 性能。
4. 在核心代码（特别是状态分析者的状态迁移逻辑、时间惩罚逻辑以及字串识别匹配词汇处）添加详细的中文注释。
